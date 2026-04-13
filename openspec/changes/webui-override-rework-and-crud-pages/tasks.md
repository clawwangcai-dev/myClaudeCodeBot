## 1. Backend: DELETE resource endpoint

- [x] 1.1 Add `delete_resource(kind, record_id)` method to `construction_agent/service.py` — soft-delete by setting status field (employees→`inactive`, vehicles→`decommissioned`, sites→`closed`)
- [x] 1.2 Add `DELETE /api/construction/resource` handler in `status_web.py` — parse `kind` and `id` query params, delegate to `delete_resource()`, return `{"ok": true, "id": "..."}` or 404/400 errors
- [x] 1.3 Test DELETE endpoint: verify soft-delete for each kind, verify 404 for missing ID, verify 400 for invalid kind

## 2. Frontend: Override modal

- [x] 2.1 Remove the inline Overrides `<section>` from `_render_construction_html()` HTML output
- [x] 2.2 Add modal HTML markup: overlay backdrop, modal container with header (title + X close button), form fields, Apply button, result `<pre>` box
- [x] 2.3 Add CSS for modal: centered overlay, backdrop blur/dim, transition animation, responsive width
- [x] 2.4 Update `prefillOverrideForm()` JS to open the modal instead of scrolling to an inline section
- [x] 2.5 Add close handlers: X button click, backdrop click, Escape key
- [x] 2.6 Update Apply Override JS to show result inside the modal and keep modal open
- [x] 2.7 Verify: assignment card selection highlight still works behind modal backdrop

## 3. Frontend: Resources page route

- [x] 3.1 Add `GET /construction/resources` route in `status_web.py` that calls `_render_resources_html()`
- [x] 3.2 Create `_render_resources_html()` function with tabbed layout (Employees | Sites | Vehicles), search input, and "Add" button per tab
- [x] 3.3 Add "Resources" navigation button in the Construction Console hero section linking to `/construction/resources`
- [x] 3.4 Add "← Back to Console" link on the resources page to return to `/construction`

## 4. Frontend: Resource table rendering

- [x] 4.1 Implement Employees tab: fetch from `GET /api/construction/resources?kind=employees`, render table with columns Name, Role, Primary Skill, Certificates, Can Drive, Can Lead, Status
- [x] 4.2 Implement Sites tab: fetch from `GET /api/construction/resources?kind=sites`, render table with columns Name, Code, Address, Headcount, Risk Level, Urgency, Priority
- [x] 4.3 Implement Vehicles tab: fetch from `GET /api/construction/resources?kind=vehicles`, render table with columns Code, Plate Number, Type, Seats, Status, Maintenance
- [x] 4.4 Add client-side search/filter: JS `Array.filter` on rendered table rows matching against visible column text

## 5. Frontend: Resource CRUD interactions

- [x] 5.1 Inline edit: clicking "Edit" converts row to input fields, changes buttons to "Save" / "Cancel"
- [x] 5.2 Save edit: POST updated record to `/api/construction/resource`, restore read-only on success, show error on failure
- [x] 5.3 Cancel edit: restore original values and read-only mode
- [x] 5.4 Add new record: "Add" button inserts editable empty row at top, Save POSTs to same upsert endpoint
- [x] 5.5 Delete record: "Delete" shows `confirm()` dialog, calls `DELETE /api/construction/resource?kind=X&id=Y`, removes row on success

## 6. Integration testing

- [x] 6.1 Verify Override modal: open via Prepare Override, pre-fill, apply, close via X/backdrop/Escape
- [x] 6.2 Verify Resources CRUD: list, search, add, edit, delete for all three resource kinds
- [x] 6.3 Verify soft-delete: deleted records no longer appear in resource lists but remain in database for audit
