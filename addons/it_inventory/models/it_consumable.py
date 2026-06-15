from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ItConsumable(models.Model):
    _name = 'it.consumable'
    _description = 'IT Consumable'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Consumable Name', required=True, tracking=True)
    category = fields.Selection([
        ('toner', 'Toner / Ink Cartridge'),
        ('battery', 'Battery'),
        ('cable', 'Cable / Connector'),
        ('cleaning', 'Cleaning Supplies'),
        ('storage_media', 'Storage Media (USB / DVD)'),
        ('keyboard_mouse', 'Keyboard / Mouse'),
        ('power', 'Power Strip / UPS Battery'),
        ('headset', 'Headset / Earphone'),
        ('other', 'Other'),
    ], string='Category', required=True, default='other', tracking=True)

    part_number = fields.Char(string='Part / Model Number')
    description = fields.Text(string='Description')
    vendor_id = fields.Many2one('res.partner', string='Preferred Vendor')

    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure', required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
    )
    quantity_on_hand = fields.Float(
        string='Qty On Hand', default=0.0, tracking=True
    )
    reorder_qty = fields.Float(string='Reorder Level', default=5.0)
    unit_cost = fields.Monetary(
        string='Unit Cost', currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id
    )

    # Compatible with which asset types
    compatible_asset_types = fields.Many2many(
        'it.asset.category', string='Compatible Asset Categories'
    )

    issue_ids = fields.One2many(
        'it.consumable.issue', 'consumable_id', string='Issue History'
    )
    total_issued = fields.Float(
        string='Total Issued', compute='_compute_totals', store=True
    )

    needs_reorder = fields.Boolean(
        string='Below Reorder Level', compute='_compute_needs_reorder', store=True
    )
    active = fields.Boolean(default=True)

    @api.depends('issue_ids.quantity_issued')
    def _compute_totals(self):
        for con in self:
            con.total_issued = sum(con.issue_ids.mapped('quantity_issued'))

    @api.depends('quantity_on_hand', 'reorder_qty')
    def _compute_needs_reorder(self):
        for con in self:
            con.needs_reorder = con.quantity_on_hand <= con.reorder_qty

    def action_issue(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue Consumable'),
            'res_model': 'it.consumable.issue',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_consumable_id': self.id,
                'default_issue_date': fields.Date.today(),
            },
        }

    def action_receive(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receive Stock'),
            'res_model': 'it.consumable.receive.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_consumable_id': self.id},
        }


class ItConsumableIssue(models.Model):
    _name = 'it.consumable.issue'
    _description = 'Consumable Issue Record'
    _order = 'issue_date desc'

    consumable_id = fields.Many2one(
        'it.consumable', string='Consumable', required=True, ondelete='restrict'
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Issued To', required=True
    )
    asset_id = fields.Many2one(
        'it.asset', string='For Asset'
    )
    quantity_issued = fields.Float(string='Quantity', required=True, default=1.0)
    issue_date = fields.Date(
        string='Issue Date', required=True, default=fields.Date.today
    )
    issued_by = fields.Many2one(
        'res.users', string='Issued By',
        default=lambda self: self.env.user, readonly=True
    )
    notes = fields.Text(string='Notes')

    def action_confirm_issue(self):
        # Odoo saves the record before calling this; just close the dialog.
        return {'type': 'ir.actions.act_window_close'}

    @api.constrains('quantity_issued')
    def _check_quantity(self):
        for issue in self:
            if issue.quantity_issued <= 0:
                raise ValidationError(_("Quantity must be positive."))
            if issue.consumable_id.quantity_on_hand < issue.quantity_issued:
                raise ValidationError(
                    _("Insufficient stock. Available: %g %s")
                    % (issue.consumable_id.quantity_on_hand,
                       issue.consumable_id.uom_id.name)
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for issue in records:
            issue.consumable_id.quantity_on_hand -= issue.quantity_issued
            issue.consumable_id.message_post(
                body=_("%g %s issued to %s on %s.") % (
                    issue.quantity_issued,
                    issue.consumable_id.uom_id.name,
                    issue.employee_id.name,
                    issue.issue_date,
                )
            )
        return records
