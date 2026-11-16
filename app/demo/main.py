"""Standalone, dependency-light demo API for recruiter demonstrations.

This module deliberately does not import the production SQLAlchemy application.
It keeps all state in memory and exposes the same /api/v1 URL family used by
the production frontend. Restarting the process resets the demo dataset.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

app = FastAPI(title="Service Agreement Manager Demo API", version="demo-1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NOW = datetime.now(timezone.utc)


def iso(days: int = 0) -> str:
    return (NOW + timedelta(days=days)).isoformat()


def date(days: int = 0) -> str:
    return iso(days)[:10]


def uid(prefix: str) -> str:
    return f"demo-{prefix}-{uuid4().hex[:10]}"


company = {
    "id": "demo-company-1",
    "name": "Northstar HVAC Services",
    "legal_name": "Northstar HVAC Services LLC",
    "timezone": "America/Chicago",
    "currency": "USD",
    "is_active": True,
}
user = {
    "id": "demo-user-1",
    "company_id": company["id"],
    "email": "demo@northstarhvac.example",
    "full_name": "Alex Morgan",
    "role": "owner",
    "is_active": True,
}

customers = [
    {
        "id": "demo-customer-1", "company_id": company["id"], "customer_number": "CUS-1001",
        "kind": "commercial", "name": "Harborview Medical Center",
        "email": "facilities@harborview.example", "phone": "(312) 555-0148",
        "status": "active", "notes": "Priority facilities account.",
        "created_at": iso(-120), "updated_at": iso(-2),
    },
    {
        "id": "demo-customer-2", "company_id": company["id"], "customer_number": "CUS-1002",
        "kind": "commercial", "name": "Lakefront Office Group",
        "email": "ops@lakefront.example", "phone": "(312) 555-0182",
        "status": "active", "notes": "Three managed office locations.",
        "created_at": iso(-95), "updated_at": iso(-5),
    },
    {
        "id": "demo-customer-3", "company_id": company["id"], "customer_number": "CUS-1003",
        "kind": "residential", "name": "Maya Patel Residence",
        "email": "maya.patel@example", "phone": "(773) 555-0109",
        "status": "active", "notes": "Annual maintenance customer.",
        "created_at": iso(-70), "updated_at": iso(-7),
    },
    {
        "id": "demo-customer-4", "company_id": company["id"], "customer_number": "CUS-1004",
        "kind": "commercial", "name": "Riverside Manufacturing",
        "email": "maintenance@riverside.example", "phone": "(847) 555-0194",
        "status": "active", "notes": "Plant HVAC and refrigeration.",
        "created_at": iso(-45), "updated_at": iso(-1),
    },
]

locations = [
    {
        "id": "demo-location-1", "customer_id": "demo-customer-1", "name": "Main Hospital",
        "address_line1": "500 Harbor Drive", "address_line2": "Facilities entrance",
        "city": "Chicago", "region": "IL", "postal_code": "60611", "country_code": "US",
        "access_instructions": "Check in with facilities desk.", "is_active": True,
    },
    {
        "id": "demo-location-2", "customer_id": "demo-customer-2", "name": "Tower A",
        "address_line1": "220 Lake Street", "address_line2": None, "city": "Chicago",
        "region": "IL", "postal_code": "60601", "country_code": "US",
        "access_instructions": "Loading dock after 6 PM.", "is_active": True,
    },
    {
        "id": "demo-location-3", "customer_id": "demo-customer-4", "name": "Plant 1",
        "address_line1": "710 Industrial Way", "address_line2": "Building 2",
        "city": "Schaumburg", "region": "IL", "postal_code": "60173", "country_code": "US",
        "access_instructions": "PPE required.", "is_active": True,
    },
]

catalog = [
    {"id": "demo-service-1", "company_id": company["id"], "service_code": "PM-HVAC",
     "name": "Preventive HVAC Maintenance", "category": "Maintenance",
     "description": "Quarterly inspection, filter check and performance test.",
     "unit_price": "425.00", "duration_minutes": 120, "is_active": True,
     "created_at": iso(-100), "updated_at": iso(-4)},
    {"id": "demo-service-2", "company_id": company["id"], "service_code": "DIAG-01",
     "name": "Diagnostic Visit", "category": "Repair",
     "description": "On-site diagnostic and system assessment.",
     "unit_price": "185.00", "duration_minutes": 90, "is_active": True,
     "created_at": iso(-100), "updated_at": iso(-4)},
    {"id": "demo-service-3", "company_id": company["id"], "service_code": "EMERGENCY",
     "name": "Emergency Callout", "category": "Emergency",
     "description": "Priority after-hours response.", "unit_price": "650.00",
     "duration_minutes": 120, "is_active": True, "created_at": iso(-80), "updated_at": iso(-2)},
]

agreements = [
    {
        "id": "demo-agreement-1", "company_id": company["id"], "customer_id": "demo-customer-1",
        "service_location_id": "demo-location-1", "agreement_number": "AGR-2026-001",
        "title": "Harborview Comprehensive HVAC Care", "status": "active",
        "start_date": date(-35), "end_date": date(330), "billing_frequency": "quarterly",
        "currency": "USD", "auto_renew": True, "renewal_notice_days": 60,
        "terms_text": "Quarterly preventive maintenance, priority response and documented service history.",
        "total_amount": "5100.00", "accepted_by_name": "Jordan Lee", "accepted_at": iso(-30),
        "acceptance_method": "portal", "acceptance_reference": "DEMO-ACCEPT-001",
        "cancelled_at": None, "cancellation_reason": None, "rejected_at": None,
        "rejected_by_name": None, "rejection_reason": None, "version_number": 2,
        "created_at": iso(-40), "updated_at": iso(-30),
        "lines": [{"id": "demo-aline-1", "catalog_item_id": "demo-service-1",
                   "service_code": "PM-HVAC", "name": "Preventive HVAC Maintenance",
                   "description": "Quarterly service", "quantity": "12",
                   "unit_price": "425.00", "line_total": "5100.00"}],
    },
    {
        "id": "demo-agreement-2", "company_id": company["id"], "customer_id": "demo-customer-2",
        "service_location_id": "demo-location-2", "agreement_number": "AGR-2026-002",
        "title": "Lakefront Office Service Plan", "status": "proposed",
        "start_date": date(12), "end_date": date(377), "billing_frequency": "monthly",
        "currency": "USD", "auto_renew": True, "renewal_notice_days": 45,
        "terms_text": "Monthly inspection and priority service for office HVAC equipment.",
        "total_amount": "3600.00", "accepted_by_name": None, "accepted_at": None,
        "acceptance_method": None, "acceptance_reference": None, "cancelled_at": None,
        "cancellation_reason": None, "rejected_at": None, "rejected_by_name": None,
        "rejection_reason": None, "version_number": 1, "created_at": iso(-12),
        "updated_at": iso(-1),
        "lines": [{"id": "demo-aline-2", "catalog_item_id": "demo-service-1",
                   "service_code": "PM-HVAC", "name": "Preventive HVAC Maintenance",
                   "description": "Monthly service", "quantity": "8",
                   "unit_price": "450.00", "line_total": "3600.00"}],
    },
]

work_orders = [
    {"id": "demo-work-1", "company_id": company["id"], "branch_id": "demo-branch-1",
     "customer_id": "demo-customer-1", "service_location_id": "demo-location-1",
     "customer_name": "Harborview Medical Center", "customer_phone": "(312) 555-0148",
     "service_location_name": "Main Hospital", "service_location_address": "500 Harbor Drive",
     "access_instructions": "Check in with facilities desk.", "equipment_id": "demo-equipment-1",
     "agreement_id": "demo-agreement-1", "maintenance_schedule_id": None,
     "occurrence_date": date(2), "work_order_number": "WO-2026-1041",
     "title": "Quarterly rooftop inspection", "description": "Inspect three rooftop units and document readings.",
     "required_skill": "HVAC", "status": "assigned", "priority": "high",
     "scheduled_for": iso(2), "appointment_start": iso(2), "appointment_end": iso(2),
     "assigned_to_user_id": "demo-tech-1", "assigned_at": iso(-1), "started_at": None,
     "completed_at": None, "completion_notes": None, "technician_findings": None,
     "checklist_results": None, "customer_signoff_name": None, "cancellation_reason": None,
     "created_at": iso(-2), "updated_at": iso(-1)},
    {"id": "demo-work-2", "company_id": company["id"], "branch_id": "demo-branch-1",
     "customer_id": "demo-customer-2", "service_location_id": "demo-location-2",
     "customer_name": "Lakefront Office Group", "customer_phone": "(312) 555-0182",
     "service_location_name": "Tower A", "service_location_address": "220 Lake Street",
     "access_instructions": "Loading dock after 6 PM.", "equipment_id": "demo-equipment-2",
     "agreement_id": "demo-agreement-2", "maintenance_schedule_id": None,
     "occurrence_date": date(1), "work_order_number": "WO-2026-1042",
     "title": "Office air-flow diagnostic", "description": "Investigate inconsistent airflow on floor 7.",
     "required_skill": "Diagnostics", "status": "in_progress", "priority": "normal",
     "scheduled_for": iso(1), "appointment_start": iso(1), "appointment_end": iso(1),
     "assigned_to_user_id": "demo-tech-2", "assigned_at": iso(-2), "started_at": iso(0),
     "completed_at": None, "completion_notes": None, "technician_findings": "Damper actuator under inspection.",
     "checklist_results": {"safety": True, "filters": True, "controls": False},
     "customer_signoff_name": None, "cancellation_reason": None,
     "created_at": iso(-3), "updated_at": iso(0)},
    {"id": "demo-work-3", "company_id": company["id"], "branch_id": "demo-branch-1",
     "customer_id": "demo-customer-4", "service_location_id": "demo-location-3",
     "customer_name": "Riverside Manufacturing", "customer_phone": "(847) 555-0194",
     "service_location_name": "Plant 1", "service_location_address": "710 Industrial Way",
     "access_instructions": "PPE required.", "equipment_id": "demo-equipment-3",
     "agreement_id": "demo-agreement-1", "maintenance_schedule_id": None,
     "occurrence_date": date(-1), "work_order_number": "WO-2026-1038",
     "title": "Plant preventive maintenance", "description": "Quarterly PM completed.",
     "required_skill": "HVAC", "status": "completed", "priority": "normal",
     "scheduled_for": iso(-1), "appointment_start": iso(-1), "appointment_end": iso(-1),
     "assigned_to_user_id": "demo-tech-1", "assigned_at": iso(-4), "started_at": iso(-1),
     "completed_at": iso(-1), "completion_notes": "All readings within expected range.",
     "technician_findings": "Minor belt wear noted.",
     "checklist_results": {"safety": True, "filters": True, "controls": True},
     "customer_signoff_name": "Priya Shah", "cancellation_reason": None,
     "created_at": iso(-7), "updated_at": iso(-1)},
]

invoices = [
    {"id": "demo-invoice-1", "company_id": company["id"], "customer_id": "demo-customer-1",
     "service_location_id": "demo-location-1", "agreement_id": "demo-agreement-1",
     "invoice_number": "INV-2026-0201", "status": "issued", "invoice_date": date(-8),
     "due_date": date(22), "currency": "USD", "subtotal": "1275.00",
     "total_amount": "1275.00", "discount_percent": "0", "discount_amount": "0",
     "tax_percent": "0", "tax_amount": "0", "notes": "Quarterly service plan billing.",
     "issued_at": iso(-8), "voided_at": None, "void_reason": None,
     "created_at": iso(-9), "updated_at": iso(-8),
     "lines": [{"id": "demo-iline-1", "service_code": "PM-HVAC",
                "description": "Preventive HVAC Maintenance", "details": "Q2 service",
                "quantity": "3", "unit_price": "425.00", "line_total": "1275.00"}],
     "amount_paid": "0", "amount_refunded": "0", "credits_applied": "0",
     "balance_due": "1275.00", "is_overdue": False},
    {"id": "demo-invoice-2", "company_id": company["id"], "customer_id": "demo-customer-2",
     "service_location_id": "demo-location-2", "agreement_id": "demo-agreement-2",
     "invoice_number": "INV-2026-0196", "status": "partially_paid", "invoice_date": date(-25),
     "due_date": date(-2), "currency": "USD", "subtotal": "900.00", "total_amount": "900.00",
     "discount_percent": "0", "discount_amount": "0", "tax_percent": "0", "tax_amount": "0",
     "notes": "Payment received against monthly plan.", "issued_at": iso(-25),
     "voided_at": None, "void_reason": None, "created_at": iso(-26), "updated_at": iso(-2),
     "lines": [{"id": "demo-iline-2", "service_code": "PM-HVAC", "description": "Preventive HVAC Maintenance",
                "details": "Two visits", "quantity": "2", "unit_price": "450.00", "line_total": "900.00"}],
     "amount_paid": "450.00", "amount_refunded": "0", "credits_applied": "0",
     "balance_due": "450.00", "is_overdue": True},
    {"id": "demo-invoice-3", "company_id": company["id"], "customer_id": "demo-customer-4",
     "service_location_id": "demo-location-3", "agreement_id": "demo-agreement-1",
     "invoice_number": "INV-2026-0200", "status": "paid", "invoice_date": date(-18),
     "due_date": date(12), "currency": "USD", "subtotal": "600.00", "total_amount": "600.00",
     "discount_percent": "0", "discount_amount": "0", "tax_percent": "0", "tax_amount": "0",
     "notes": None, "issued_at": iso(-18), "voided_at": None, "void_reason": None,
     "created_at": iso(-19), "updated_at": iso(-10),
     "lines": [{"id": "demo-iline-3", "service_code": "PM-HVAC", "description": "Plant preventive maintenance",
                "details": None, "quantity": "1", "unit_price": "600.00", "line_total": "600.00"}],
     "amount_paid": "600.00", "amount_refunded": "0", "credits_applied": "0",
     "balance_due": "0", "is_overdue": False},
]

equipment = [
    {"id":"demo-equipment-1","company_id":company["id"],"customer_id":"demo-customer-1","service_location_id":"demo-location-1",
     "asset_number":"AST-1001","category":"Rooftop Unit","manufacturer":"Trane","model_number":"RTU-48",
     "serial_number":"TRN-88421","installed_on":"2023-04-10","warranty_expires_on":"2028-04-10",
     "status":"active","notes":"Unit 1 north wing.","created_at":iso(-100),"updated_at":iso(-2)},
    {"id":"demo-equipment-2","company_id":company["id"],"customer_id":"demo-customer-2","service_location_id":"demo-location-2",
     "asset_number":"AST-1002","category":"Air Handler","manufacturer":"Carrier","model_number":"AHU-20",
     "serial_number":"CAR-55210","installed_on":"2022-08-12","warranty_expires_on":"2027-08-12",
     "status":"active","notes":"Floor 7 mechanical room.","created_at":iso(-90),"updated_at":iso(-2)},
    {"id":"demo-equipment-3","company_id":company["id"],"customer_id":"demo-customer-4","service_location_id":"demo-location-3",
     "asset_number":"AST-1003","category":"Chiller","manufacturer":"York","model_number":"YC-450",
     "serial_number":"YRK-10293","installed_on":"2021-03-02","warranty_expires_on":"2027-03-02",
     "status":"active","notes":"Plant cooling loop.","created_at":iso(-80),"updated_at":iso(-1)},
]

branches = [{
    "id":"demo-branch-1","company_id":company["id"],"name":"Chicago Central","code":"CHI",
    "timezone":"America/Chicago","address_line1":"100 Service Way","address_line2":None,
    "city":"Chicago","region":"IL","postal_code":"60606","country_code":"US",
    "phone":"(312) 555-0100","email":"dispatch@northstar.example","is_primary":True,
    "is_active":True,"created_at":iso(-120),"updated_at":iso(-2),
}]

def collection(name: str) -> list[dict[str, Any]]:
    return {
        "customers": customers, "equipment": equipment, "service-catalog": catalog,
        "agreements": agreements, "work-orders": work_orders, "invoices": invoices,
        "branches": branches,
    }.get(name, [])


def find_item(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    return next((item for item in items if item["id"] == item_id), None)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"name": app.title, "mode": "in-memory-demo", "database": "none"}


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def demo_api(path: str, request: Request):
    parts = [p for p in path.split("/") if p]
    method = request.method
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}

    if path in {"auth/login", "auth/register"}:
        return {"authenticated": True, "expires_in": 3600}
    if path == "auth/me":
        return deepcopy(user)
    if path.startswith("auth/"):
        return {} if method != "GET" else {"message": "demo"}
    if path == "companies/current":
        if method in {"PATCH", "PUT"}:
            company.update(body)
        return deepcopy(company)

    if parts and parts[0] in {"customers", "equipment", "service-catalog", "agreements", "work-orders", "invoices", "branches"}:
        resource = parts[0]
        items = collection(resource)
        if len(parts) == 1:
            if method == "GET":
                return deepcopy(items)
            if method == "POST":
                new = deepcopy(body)
                new["id"] = uid(resource[:-1] if resource.endswith("s") else resource)
                new.setdefault("company_id", company["id"])
                new.setdefault("created_at", iso())
                new.setdefault("updated_at", iso())
                if resource == "customers":
                    new.update({"customer_number": new.get("customer_number", f"CUS-{len(items)+2000}"), "status": "active"})
                elif resource == "equipment":
                    new.update({"asset_number": new.get("asset_number", f"AST-{len(items)+2000}"), "status": "active"})
                elif resource == "agreements":
                    new.update({"agreement_number": new.get("agreement_number", f"AGR-DEMO-{len(items)+2000}"), "status": "draft", "version_number": 1, "lines": []})
                elif resource == "work-orders":
                    new.update({"work_order_number": new.get("work_order_number", f"WO-DEMO-{len(items)+2000}"), "status": "scheduled"})
                elif resource == "invoices":
                    total = new.get("total_amount", new.get("subtotal", "0"))
                    new.update({"invoice_number": new.get("invoice_number", f"INV-DEMO-{len(items)+2000}"), "status": "draft",
                                "currency": "USD", "total_amount": total, "subtotal": total,
                                "amount_paid": "0", "amount_refunded": "0", "credits_applied": "0",
                                "balance_due": total, "is_overdue": False, "lines": []})
                elif resource == "branches":
                    new.update({"code": new.get("code", f"BR-{len(items)+2000}"), "is_active": True, "is_primary": False})
                items.insert(0, new)
                return deepcopy(new)

        item = find_item(items, parts[1]) if len(parts) > 1 else None
        if item is None:
            return JSONResponse({"error": {"code": "not_found", "message": "Demo record not found"}}, status_code=404)

        if resource == "customers" and len(parts) >= 3:
            if parts[2] == "contacts":
                return []
            if parts[2] == "service-locations":
                if method == "POST":
                    new = deepcopy(body)
                    new.update({"id": uid("location"), "customer_id": item["id"], "is_active": True})
                    locations.append(new)
                    return new
                return deepcopy([x for x in locations if x["customer_id"] == item["id"]])
        if resource == "agreements" and len(parts) >= 3:
            if parts[2] == "versions":
                return [{"version_number": item.get("version_number", 1), "status": item.get("status"), "created_at": item.get("created_at")}]
            if parts[2] == "events":
                return [{"id": uid("event"), "event_type": "agreement.updated", "created_at": item.get("updated_at")}]
            if parts[2] == "renewals":
                return []
            if method == "POST":
                transitions = {"activate":"active", "accept":"accepted", "reject":"rejected", "cancel":"cancelled", "suspend":"suspended", "propose":"proposed"}
                action = parts[2]
                if action in transitions:
                    item["status"] = transitions[action]
                item["updated_at"] = iso()
                return deepcopy(item)
        if resource == "work-orders" and len(parts) >= 3:
            if parts[2] == "events":
                return [{"id": uid("event"), "event_type": "work_order.updated", "created_at": item.get("updated_at")}]
            if method == "POST":
                transitions = {"assign":"assigned", "start":"in_progress", "complete":"completed", "cancel":"cancelled", "schedule":"scheduled"}
                action = parts[2]
                if action in transitions:
                    item["status"] = transitions[action]
                item["updated_at"] = iso()
                return deepcopy(item)
        if resource == "invoices" and len(parts) >= 3:
            action = parts[2]
            if action == "payments" and method == "GET":
                return [{"id": uid("payment"), "invoice_id": item["id"], "amount": item.get("amount_paid", "0"),
                         "payment_method": "bank_transfer", "reference": "DEMO-REF", "received_at": iso(-3), "refunds": []}]
            if action in {"credits", "events"}:
                return []
            if method == "POST":
                if action == "issue":
                    item["status"] = "issued"; item["issued_at"] = iso()
                elif action == "void":
                    item["status"] = "void"; item["voided_at"] = iso(); item["void_reason"] = body.get("reason", "Demo void")
                item["updated_at"] = iso()
                return deepcopy(item)

        if method == "PATCH":
            item.update(body)
            item["updated_at"] = iso()
        elif method == "DELETE":
            item["status"] = "inactive"
            item["updated_at"] = iso()
            return Response(status_code=204)
        return deepcopy(item)

    if path == "reports/agreements/summary":
        return {"active": sum(x["status"] == "active" for x in agreements),
                "proposed": sum(x["status"] == "proposed" for x in agreements),
                "draft": sum(x["status"] == "draft" for x in agreements)}
    if path == "reports/billing/receivables":
        outstanding = sum(float(x["balance_due"]) for x in invoices)
        overdue = sum(float(x["balance_due"]) for x in invoices if x["is_overdue"])
        return {"total_outstanding": f"{outstanding:.2f}", "overdue": f"{overdue:.2f}", "currency": "USD"}
    if path == "reports/work-orders":
        return {status: sum(x["status"] == status for x in work_orders)
                for status in ("scheduled", "assigned", "in_progress", "completed")}
    if path == "team/technicians":
        return [
            {"id":"demo-tech-1","email":"jordan.tech@northstar.example","full_name":"Jordan Brooks",
             "is_active":True,"skills":["HVAC","Commercial"],"branch_ids":["demo-branch-1"],"branch_names":["Chicago Central"]},
            {"id":"demo-tech-2","email":"casey.tech@northstar.example","full_name":"Casey Nguyen",
             "is_active":True,"skills":["Diagnostics"],"branch_ids":["demo-branch-1"],"branch_names":["Chicago Central"]},
        ]
    if path in {"team/invitations", "notifications", "sms", "webhooks", "recurring-invoices", "maintenance/schedules"}:
        return []
    if path.startswith("customer-portal/"):
        return customer_portal(path)
    if path.startswith("agreement-portal/public/"):
        return agreement_portal()
    if path.startswith("invoice-portal/public/"):
        invoice = invoices[0]
        return {"invoice_number":invoice["invoice_number"],"company_name":company["name"],"customer_name":customers[0]["name"],
                "recipient_name":"Jordan Lee","recipient_email":"jordan.lee@harborview.example","invoice_date":invoice["invoice_date"],
                "due_date":invoice["due_date"],"issued_at":invoice["issued_at"],"currency":"USD","status":invoice["status"],
                "subtotal":invoice["subtotal"],"discount_amount":"0","tax_amount":"0","total_amount":invoice["total_amount"],
                "amount_paid":invoice["amount_paid"],"amount_refunded":"0","credits_applied":"0","balance_due":invoice["balance_due"],
                "notes":invoice["notes"],"expires_at":iso(7),"portal_status":"payable","lines":invoice["lines"]}
    if path.startswith("exports/"):
        return Response("id,number,status\ndemo,DEMO,active\n", media_type="text/csv")
    return {}


def customer_portal(path: str) -> Any:
    if path.endswith("/auth/me") or path.endswith("/auth/login"):
        return {"id":"demo-portal-user","email":"facilities@harborview.example","full_name":"Jordan Lee",
                "memberships":[{"membership_id":"demo-membership-1","customer_id":"demo-customer-1",
                                "company_id":company["id"],"company_name":company["name"],
                                "customer_name":customers[0]["name"]}]}
    if path.endswith("/overview"):
        return {"company_name":company["name"],"customer_name":customers[0]["name"],
                "customer_number":customers[0]["customer_number"],"customer_kind":customers[0]["kind"],
                "locations":deepcopy(locations[:1]),"agreement_count":1,"open_work_order_count":1,"unpaid_invoice_count":1}
    if path.endswith("/agreements"):
        return deepcopy(agreements[:1])
    if path.endswith("/locations"):
        return deepcopy(locations[:1])
    if path.endswith("/equipment"):
        return deepcopy(equipment[:1])
    if path.endswith("/work-orders"):
        return deepcopy(work_orders[:1])
    if path.endswith("/invoices"):
        return deepcopy(invoices[:1])
    if path.endswith("/payments") or path.endswith("/documents"):
        return []
    return {}


def agreement_portal() -> dict[str, Any]:
    agreement = agreements[0]
    return {
        "agreement_number":agreement["agreement_number"],"title":agreement["title"],"company_name":company["name"],
        "customer_name":customers[0]["name"],"recipient_name":"Jordan Lee","recipient_email":"jordan.lee@harborview.example",
        "service_location_name":locations[0]["name"],"service_location_city":locations[0]["city"],
        "service_location_region":locations[0]["region"],"service_location_country":"US",
        "start_date":agreement["start_date"],"end_date":agreement["end_date"],
        "billing_frequency":agreement["billing_frequency"],"currency":"USD","auto_renew":True,
        "terms_text":agreement["terms_text"],"total_amount":agreement["total_amount"],"version_number":2,
        "expires_at":iso(7),"portal_status":"pending","accepted_at":None,"rejected_at":None,
        "rejection_reason":None,"lines":agreement["lines"],
    }
