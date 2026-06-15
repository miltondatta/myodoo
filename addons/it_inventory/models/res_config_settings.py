from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    it_warranty_warning_days = fields.Integer(
        string='Warranty Warning (Days)',
        config_parameter='it_inventory.warranty_warning_days',
        default=30,
        help='Send warranty expiry alerts this many days before expiry.'
    )
    it_amc_warning_days = fields.Integer(
        string='AMC Expiry Warning (Days)',
        config_parameter='it_inventory.amc_warning_days',
        default=30,
    )
    it_license_warning_days = fields.Integer(
        string='License Expiry Warning (Days)',
        config_parameter='it_inventory.license_warning_days',
        default=30,
    )
    it_auto_create_assets = fields.Boolean(
        string='Auto-create Assets from PO Receipts',
        config_parameter='it_inventory.auto_create_assets',
        default=True,
        help='Automatically create draft IT assets when PO receipts are validated '
             'for products mapped to IT asset categories.'
    )
    it_require_approval = fields.Boolean(
        string='Require Approval for Asset Requests',
        config_parameter='it_inventory.require_approval',
        default=True,
    )
