{
    'name': 'IT Asset Management (ITAM)',
    'version': '19.0.2.0.0',
    'summary': 'Enterprise-grade IT Asset Management — lifecycle, licensing, audits, requests',
    'description': """
IT Asset Management (ITAM) — Enterprise Edition for Odoo Community
==================================================================
Complete IT Asset lifecycle management:

Phase 1 — Core ITAM
  • 10-state lifecycle (Draft → In Stock → Assigned → ... → Disposed)
  • Asset categories, locations, serial numbers, barcodes, QR codes
  • Assignment history with chatter tracking
  • Warranty & AMC contract tracking with email alerts

Phase 2 — Workflow & Licensing
  • Asset request & approval workflow
  • Software license management with seat tracking
  • Consumables stock & issuance
  • IT support ticket system

Phase 3 — Integrations & Audit
  • HR: employee asset smart buttons, onboarding/offboarding
  • Purchase: auto-create assets from received PO products
  • Maintenance: repair tracking linked to assets
  • Asset audit & physical verification

Phase 4 — Reporting & KPIs
  • Depreciation tracking
  • Dashboard with KPIs
  • Asset inventory & lifecycle reports
    """,
    'author': 'Milton',
    'website': 'https://www.pentabd.com',
    'category': 'Tools/IT',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
        'purchase',
        'stock',
        'maintenance',
        'account',
        'uom',
    ],
    'data': [
        # Security — always first
        'security/it_security_groups.xml',
        'security/ir.model.access.csv',
        'security/it_record_rules.xml',
        # Sequences & seed data
        'data/it_sequence_data.xml',
        'data/it_asset_category_data.xml',
        # Views — config before main
        'views/it_asset_category_views.xml',
        'views/it_asset_location_views.xml',
        'views/it_amc_views.xml',
        'views/it_asset_views.xml',
        'views/it_asset_request_views.xml',
        'views/it_asset_audit_views.xml',
        'views/it_software_license_views.xml',
        'views/it_consumable_views.xml',
        'views/it_ticket_views.xml',
        'views/hr_employee_views.xml',
        # Wizard views
        'wizards/it_asset_assign_wizard_views.xml',
        'wizards/it_asset_return_wizard_views.xml',
        # Menus last (depends on actions defined in views)
        'views/menu_views.xml',
        # Mail templates & cron
        'data/it_mail_templates.xml',
        'data/it_scheduled_actions.xml',
        # Reports
        'report/it_asset_report.xml',
        'report/it_asset_report_template.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
