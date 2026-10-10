from datetime import date


def register(client, email, company_name):
    response = client.post("/api/v1/auth/register", json={
        "company_name": company_name,
        "full_name": "Branch Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_branch(client, headers, code="HQ", **overrides):
    payload = {
        "name": "Head Office",
        "code": code,
        "timezone": "America/Chicago",
        "city": "Austin",
        "country_code": "us",
        **overrides,
    }
    return client.post("/api/v1/branches", headers=headers, json=payload)


def test_branch_crud_primary_and_tenant_isolation(client):
    headers = register(client, "branch-owner@example.com", "Branch HVAC")
    other_headers = register(client, "branch-other@example.com", "Other HVAC")

    created = make_branch(client, headers, "hq")
    assert created.status_code == 201, created.text
    branch = created.json()
    branch_id = branch["id"]
    assert branch["code"] == "HQ"
    assert branch["country_code"] == "US"
    assert branch["timezone"] == "America/Chicago"
    assert branch["is_primary"] is True
    assert len(client.get(f"/api/v1/branches/{branch_id}/business-hours", headers=headers).json()) == 7
    unprimary_only = client.patch(f"/api/v1/branches/{branch_id}", headers=headers, json={"is_primary": False})
    assert unprimary_only.status_code == 409
    assert client.get(f"/api/v1/branches/{branch_id}", headers=headers).json()["is_primary"] is True

    second = make_branch(client, headers, "WEST", name="West Office", city="Dallas")
    assert second.status_code == 201, second.text
    assert second.json()["is_primary"] is False
    promoted = client.patch(f"/api/v1/branches/{second.json()['id']}", headers=headers, json={"is_primary": True})
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["is_primary"] is True
    first_after = client.get(f"/api/v1/branches/{branch_id}", headers=headers).json()
    assert first_after["is_primary"] is False

    third = make_branch(client, headers, "EAST", name="East Office", is_primary=True)
    assert third.status_code == 201, third.text
    assert third.json()["is_primary"] is True
    second_after = client.get(f"/api/v1/branches/{second.json()['id']}", headers=headers).json()
    assert second_after["is_primary"] is False

    demoted = client.patch(f"/api/v1/branches/{third.json()['id']}", headers=headers, json={"is_primary": False})
    assert demoted.status_code == 200, demoted.text
    primaries = [item for item in client.get("/api/v1/branches", headers=headers).json() if item["is_primary"]]
    assert len(primaries) == 1

    duplicate = make_branch(client, headers, "west", name="Duplicate Code")
    assert duplicate.status_code == 409
    invalid_timezone = make_branch(client, headers, "BADTZ", name="Invalid Time Zone", timezone="Mars/Olympus")
    assert invalid_timezone.status_code == 422

    assert client.get(f"/api/v1/branches/{branch_id}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/branches", headers=other_headers).json() == []


def test_business_hours_replace_requires_one_valid_entry_for_each_day(client):
    headers = register(client, "hours-owner@example.com", "Business Hours HVAC")
    created = make_branch(client, headers, "MAIN")
    assert created.status_code == 201, created.text
    branch_id = created.json()["id"]
    defaults = client.get(f"/api/v1/branches/{branch_id}/business-hours", headers=headers)
    assert defaults.status_code == 200
    assert [item["day_of_week"] for item in defaults.json()] == list(range(7))
    assert all(item["is_closed"] for item in defaults.json())

    hours = []
    for day in range(7):
        if day < 5:
            hours.append({
                "day_of_week": day,
                "is_closed": False,
                "opens_at": "09:00:00",
                "closes_at": "17:00:00",
            })
        else:
            hours.append({"day_of_week": day, "is_closed": True})
    saved = client.put(
        f"/api/v1/branches/{branch_id}/business-hours",
        headers=headers,
        json={"hours": hours},
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()) == 7
    assert saved.json()[0]["opens_at"] == "09:00:00"
    assert saved.json()[4]["closes_at"] == "17:00:00"
    assert saved.json()[5]["is_closed"] is True
    assert saved.json()[5]["opens_at"] is None

    duplicate_days = [{"day_of_week": day, "is_closed": True} for day in range(6)]
    duplicate_days.append({"day_of_week": 5, "is_closed": True})
    assert client.put(
        f"/api/v1/branches/{branch_id}/business-hours",
        headers=headers,
        json={"hours": duplicate_days},
    ).status_code == 422

    invalid_window = [
        {
            "day_of_week": day,
            "is_closed": False,
            "opens_at": "09:00:00",
            "closes_at": "09:00:00",
        } if day == 0 else {"day_of_week": day, "is_closed": True}
        for day in range(7)
    ]
    assert client.put(
        f"/api/v1/branches/{branch_id}/business-hours",
        headers=headers,
        json={"hours": invalid_window},
    ).status_code == 422


def test_branch_closures_are_date_scoped_unique_and_tenant_safe(client):
    headers = register(client, "closures-owner@example.com", "Closure HVAC")
    other_headers = register(client, "closures-other@example.com", "Other Closure HVAC")
    created = make_branch(client, headers, "SOUTH", name="South Office")
    assert created.status_code == 201, created.text
    branch_id = created.json()["id"]
    closure_date = date(2027, 1, 1).isoformat()

    closure = client.post(f"/api/v1/branches/{branch_id}/closures", headers=headers, json={
        "closure_date": closure_date,
        "name": "New Year Holiday",
        "description": "Office closed for the public holiday",
    })
    assert closure.status_code == 201, closure.text
    closure_id = closure.json()["id"]
    assert closure.json()["closure_date"] == closure_date

    duplicate = client.post(f"/api/v1/branches/{branch_id}/closures", headers=headers, json={
        "closure_date": closure_date, "name": "Duplicate Holiday",
    })
    assert duplicate.status_code == 409

    listed = client.get(
        f"/api/v1/branches/{branch_id}/closures?from_date=2027-01-01&through_date=2027-12-31",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get(f"/api/v1/branches/{branch_id}/closures?from_date=2027-12-31&through_date=2027-01-01", headers=headers).status_code == 422

    assert client.get(f"/api/v1/branches/{branch_id}/closures", headers=other_headers).status_code == 404
    assert client.delete(f"/api/v1/branches/{branch_id}/closures/{closure_id}", headers=other_headers).status_code == 404
    assert client.delete(f"/api/v1/branches/{branch_id}/closures/{closure_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/branches/{branch_id}/closures", headers=headers).json() == []
