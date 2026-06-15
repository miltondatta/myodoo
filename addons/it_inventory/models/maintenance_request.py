from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    it_asset_id = fields.Many2one(
        'it.asset', string='IT Asset', ondelete='set null', index=True,
        tracking=True
    )
    it_asset_tag = fields.Char(
        string='Asset Tag', related='it_asset_id.asset_tag', readonly=True
    )
    it_asset_serial = fields.Char(
        string='Serial Number', related='it_asset_id.serial_number', readonly=True
    )
