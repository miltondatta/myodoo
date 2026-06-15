from odoo import fields, models


class ItAsset(models.Model):
    _name = 'it.asset'
    _description = 'IT Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Asset Name', required=True, tracking=True)
    serial_number = fields.Char(string='Serial Number', tracking=True)
    asset_type = fields.Selection([
        ('computer', 'Computer / Desktop'),
        ('laptop', 'Laptop'),
        ('server', 'Server'),
        ('networking', 'Networking Equipment'),
        ('peripheral', 'Peripheral / Accessory'),
        ('software', 'Software License'),
        ('other', 'Other'),
    ], string='Asset Type', required=True, default='computer', tracking=True)
    brand = fields.Char(string='Brand / Manufacturer')
    model_number = fields.Char(string='Model Number')
    purchase_date = fields.Date(string='Purchase Date')
    warranty_date = fields.Date(string='Warranty Expiry')
    assigned_to = fields.Many2one('res.partner', string='Assigned To', tracking=True)
    state = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('repair', 'Under Repair'),
        ('retired', 'Retired'),
    ], string='Status', default='available', required=True, tracking=True)
    notes = fields.Text(string='Notes')

    def action_set_available(self):
        self.write({'state': 'available'})

    def action_set_assigned(self):
        self.write({'state': 'assigned'})

    def action_set_repair(self):
        self.write({'state': 'repair'})

    def action_set_retired(self):
        self.write({'state': 'retired'})
