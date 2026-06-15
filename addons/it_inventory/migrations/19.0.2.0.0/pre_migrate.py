"""
Pre-migration v1 → v2.

1. Removes stale ir.ui.view records for it.asset (v1 had 'assigned_to' field,
   v2 uses 'employee_id'; the views must be recreated cleanly).

   NOTE: ir_ui_view has NO 'module' column — module ownership is stored in
   ir_model_data. All queries use ir_model_data to filter by module.

2. Backfills NULL values for columns that now carry NOT NULL constraints,
   so Odoo can apply those constraints without failing on existing rows.
"""


def migrate(cr, version):
    if not version:
        return  # fresh install — nothing to clean up

    # ── 1. Delete stale it.asset views ───────────────────────────────────────
    # ir_ui_view has no 'module' column; ownership lives in ir_model_data.
    cr.execute("""
        SELECT d.res_id
        FROM ir_model_data d
        JOIN ir_ui_view v ON v.id = d.res_id
        WHERE d.model = 'ir.ui.view'
          AND d.module = 'it_inventory'
          AND v.model = 'it.asset'
    """)
    view_ids = [row[0] for row in cr.fetchall()]

    if view_ids:
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE model = 'ir.ui.view'
              AND module = 'it_inventory'
              AND res_id = ANY(%s)
        """, (view_ids,))
        cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (view_ids,))

    # ── 2. Backfill NULLs so NOT NULL constraints can be added ───────────────

    cr.execute("""
        UPDATE it_asset_category SET name = 'Uncategorised' WHERE name IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_category SET asset_type = 'other' WHERE asset_type IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_location SET name = 'Unknown Location' WHERE name IS NULL
    """)
    cr.execute("""
        UPDATE it_amc SET name = 'AMC-UNKNOWN' WHERE name IS NULL
    """)
    cr.execute("""
        UPDATE it_amc
        SET vendor_id = (SELECT id FROM res_partner LIMIT 1)
        WHERE vendor_id IS NULL
    """)
    cr.execute("""
        UPDATE it_amc SET start_date = CURRENT_DATE WHERE start_date IS NULL
    """)
    cr.execute("""
        UPDATE it_amc
        SET end_date = CURRENT_DATE + INTERVAL '1 year'
        WHERE end_date IS NULL
    """)
    cr.execute("""
        UPDATE it_asset
        SET category_id = (SELECT id FROM it_asset_category LIMIT 1)
        WHERE category_id IS NULL
          AND EXISTS (SELECT 1 FROM it_asset_category LIMIT 1)
    """)
    cr.execute("""
        UPDATE it_asset
        SET company_id = (SELECT id FROM res_company LIMIT 1)
        WHERE company_id IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_assignment
        SET assigned_date = CURRENT_DATE WHERE assigned_date IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_assignment SET state = 'active' WHERE state IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_request
        SET request_date = CURRENT_DATE WHERE request_date IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_request
        SET purpose = 'New requirement' WHERE purpose IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_request SET state = 'draft' WHERE state IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_audit
        SET audit_date = CURRENT_DATE WHERE audit_date IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_audit SET scope = 'all' WHERE scope IS NULL
    """)
    cr.execute("""
        UPDATE it_asset_audit_line SET condition = 'good' WHERE condition IS NULL
    """)
    cr.execute("""
        UPDATE it_software_license
        SET name = 'Unknown License' WHERE name IS NULL
    """)
    cr.execute("""
        UPDATE it_software_license
        SET license_type = 'perpetual' WHERE license_type IS NULL
    """)
    cr.execute("""
        UPDATE it_consumable
        SET name = 'Unknown Consumable' WHERE name IS NULL
    """)
    cr.execute("""
        UPDATE it_consumable SET category = 'other' WHERE category IS NULL
    """)
    cr.execute("""
        UPDATE it_consumable
        SET uom_id = (
            SELECT id FROM uom_uom
            WHERE name ILIKE '%unit%'
            LIMIT 1
        )
        WHERE uom_id IS NULL
    """)
    cr.execute("""
        UPDATE it_consumable_issue
        SET quantity_issued = 1 WHERE quantity_issued IS NULL
    """)
    cr.execute("""
        UPDATE it_consumable_issue
        SET issue_date = CURRENT_DATE WHERE issue_date IS NULL
    """)
    cr.execute("""
        UPDATE it_ticket SET name = 'Unknown Issue' WHERE name IS NULL
    """)
    cr.execute("""
        UPDATE it_ticket SET category = 'hardware' WHERE category IS NULL
    """)
