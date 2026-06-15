from datetime import date, timedelta
from odoo import api, fields, models, _


class ItAmc(models.Model):
    _name = 'it.amc'
    _description = 'Annual Maintenance Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'end_date'

    name = fields.Char(
        string='Contract Reference', required=True, copy=False,
        default='New', tracking=True
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor / Service Provider',
        required=True, tracking=True
    )
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    cost = fields.Monetary(string='Contract Cost', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id
    )
    coverage_type = fields.Selection([
        ('comprehensive', 'Comprehensive (Parts + Labour)'),
        ('labour', 'Labour Only'),
        ('parts', 'Parts Only'),
        ('on_site', 'On-Site Support'),
        ('remote', 'Remote Support'),
    ], string='Coverage Type', default='comprehensive', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', compute='_compute_state',
        store=True, tracking=True)

    asset_ids = fields.Many2many(
        'it.asset', 'it_amc_asset_rel', 'amc_id', 'asset_id',
        string='Covered Assets'
    )
    asset_count = fields.Integer(compute='_compute_asset_count')

    terms = fields.Html(string='Terms & Conditions')
    po_id = fields.Many2one('purchase.order', string='Purchase Order')
    notes = fields.Text(string='Internal Notes')
    active = fields.Boolean(default=True)

    days_to_expiry = fields.Integer(
        string='Days to Expiry', compute='_compute_days_to_expiry', store=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('it.amc') or 'New'
        return super().create(vals_list)

    @api.depends('end_date')
    def _compute_days_to_expiry(self):
        today = date.today()
        for amc in self:
            if amc.end_date:
                amc.days_to_expiry = (amc.end_date - today).days
            else:
                amc.days_to_expiry = 0

    @api.depends('start_date', 'end_date', 'days_to_expiry')
    def _compute_state(self):
        today = date.today()
        warning_days = int(
            self.env['ir.config_parameter'].sudo()
            .get_param('it_inventory.amc_warning_days', 30)
        )
        for amc in self:
            if not amc.start_date or not amc.end_date:
                amc.state = 'draft'
            elif amc.end_date < today:
                amc.state = 'expired'
            elif amc.end_date <= today + timedelta(days=warning_days):
                amc.state = 'expiring'
            elif amc.start_date <= today:
                amc.state = 'active'
            else:
                amc.state = 'draft'

    def _compute_asset_count(self):
        for amc in self:
            amc.asset_count = len(amc.asset_ids)

    def action_activate(self):
        for amc in self:
            amc.write({'state': 'active'})
            amc.message_post(body=_('AMC contract activated.'))

    def action_cancel(self):
        for amc in self:
            amc.write({'state': 'cancelled'})
            amc.message_post(body=_('AMC contract cancelled.'))

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Covered Assets'),
            'res_model': 'it.asset',
            'view_mode': 'list,form',
            'domain': [('amc_id', '=', self.id)],
        }
