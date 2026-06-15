from datetime import date, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ItSoftwareLicense(models.Model):
    _name = 'it.software.license'
    _description = 'Software License'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Software Name', required=True, tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', tracking=True)
    version = fields.Char(string='Version')
    license_key = fields.Char(string='License Key', copy=False)
    license_type = fields.Selection([
        ('perpetual', 'Perpetual'),
        ('subscription', 'Annual Subscription'),
        ('monthly', 'Monthly Subscription'),
        ('oem', 'OEM / Device-Bound'),
        ('open_source', 'Open Source'),
        ('freeware', 'Freeware'),
        ('trial', 'Trial'),
    ], string='License Type', required=True, default='perpetual', tracking=True)

    purchase_date = fields.Date(string='Purchase Date')
    expiry_date = fields.Date(string='Expiry / Renewal Date', tracking=True)
    cost = fields.Monetary(string='License Cost', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id
    )
    po_id = fields.Many2one('purchase.order', string='Purchase Order')

    total_seats = fields.Integer(string='Total Seats / Licenses', default=1)
    used_seats = fields.Integer(
        string='Used Seats', compute='_compute_used_seats', store=True
    )
    available_seats = fields.Integer(
        string='Available Seats', compute='_compute_used_seats', store=True
    )

    asset_ids = fields.Many2many(
        'it.asset', 'it_asset_software_rel',
        'license_id', 'asset_id', string='Installed On Assets'
    )
    employee_ids = fields.Many2many(
        'hr.employee', 'it_software_employee_rel',
        'license_id', 'employee_id', string='Assigned To Employees'
    )

    license_status = fields.Selection([
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('over_limit', 'Over Seat Limit'),
        ('inactive', 'Inactive'),
    ], string='License Status', compute='_compute_license_status', store=True, tracking=True)

    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    @api.depends('asset_ids', 'employee_ids', 'total_seats')
    def _compute_used_seats(self):
        for lic in self:
            used = max(len(lic.asset_ids), len(lic.employee_ids))
            lic.used_seats = used
            lic.available_seats = max(0, lic.total_seats - used)

    @api.depends('expiry_date', 'license_type', 'used_seats', 'total_seats')
    def _compute_license_status(self):
        today = date.today()
        warn_days = int(
            self.env['ir.config_parameter'].sudo()
            .get_param('it_inventory.license_warning_days', 30)
        )
        for lic in self:
            if lic.used_seats > lic.total_seats:
                lic.license_status = 'over_limit'
            elif lic.license_type in ('subscription', 'monthly', 'trial') and lic.expiry_date:
                if lic.expiry_date < today:
                    lic.license_status = 'expired'
                elif lic.expiry_date <= today + timedelta(days=warn_days):
                    lic.license_status = 'expiring'
                else:
                    lic.license_status = 'active'
            else:
                lic.license_status = 'active'

    @api.constrains('used_seats', 'total_seats')
    def _check_seat_limit(self):
        for lic in self:
            if lic.used_seats > lic.total_seats and lic.total_seats > 0:
                raise ValidationError(
                    _("License '%s' has exceeded its seat limit (%d used / %d allowed).")
                    % (lic.name, lic.used_seats, lic.total_seats)
                )

    @api.model
    def cron_send_license_alerts(self):
        warn_days = int(
            self.env['ir.config_parameter'].sudo()
            .get_param('it_inventory.license_warning_days', 30)
        )
        today = date.today()
        threshold = today + timedelta(days=warn_days)
        expiring = self.search([
            ('expiry_date', '>=', today.isoformat()),
            ('expiry_date', '<=', threshold.isoformat()),
            ('license_type', 'in', ['subscription', 'monthly', 'trial']),
        ])
        template = self.env.ref(
            'it_inventory.email_template_license_expiry',
            raise_if_not_found=False
        )
        if template:
            for lic in expiring:
                template.send_mail(lic.id, force_send=False)
