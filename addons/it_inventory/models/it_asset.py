import base64
import struct
from datetime import date, timedelta
from io import BytesIO
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import qrcode
    _HAS_QRCODE = True
except ImportError:
    _HAS_QRCODE = False


def _make_qr_png_fallback(text):
    """Generate a minimal 1x1 white PNG placeholder when qrcode isn't installed."""
    # 1-pixel white PNG — keeps the Binary field non-empty so the widget renders
    b64 = (
        b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
        b'z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=='
    )
    return b64


class ItAsset(models.Model):
    _name = 'it.asset'
    _description = 'IT Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'asset_tag, name'

    # ── Identity ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Asset Name', required=True, tracking=True, index=True
    )
    asset_tag = fields.Char(
        string='Asset Tag', copy=False, tracking=True, index=True,
        help='Auto-generated unique tag. Also used as barcode.'
    )
    serial_number = fields.Char(
        string='Serial Number', tracking=True, index=True, copy=False
    )
    barcode = fields.Char(
        string='Barcode / QR Data', copy=False, index=True
    )
    qr_code = fields.Binary(
        string='QR Code Image', attachment=True, copy=False
    )
    color = fields.Integer(string='Kanban Color', default=0)
    active = fields.Boolean(default=True)

    # ── Classification ────────────────────────────────────────────────────────
    category_id = fields.Many2one(
        'it.asset.category', string='Category',
        required=True, ondelete='restrict', tracking=True
    )
    asset_type = fields.Selection(
        related='category_id.asset_type', store=True, readonly=True
    )
    brand = fields.Char(string='Brand / Manufacturer')
    model_number = fields.Char(string='Model Number')
    description = fields.Html(string='Description')
    specifications = fields.Text(string='Technical Specifications')
    image = fields.Binary(string='Asset Photo', attachment=True)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_stock', 'In Stock'),
        ('reserved', 'Reserved'),
        ('assigned', 'Assigned'),
        ('under_repair', 'Under Repair'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
        ('returned', 'Returned'),
        ('retired', 'Retired'),
        ('disposed', 'Disposed'),
    ], string='Status', default='draft', required=True,
        tracking=True, index=True)

    # ── Assignment ────────────────────────────────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Assigned To',
        tracking=True, domain="[('active', '=', True)]"
    )
    department_id = fields.Many2one(
        'hr.department', string='Department', tracking=True
    )
    location_id = fields.Many2one(
        'it.asset.location', string='Location', tracking=True
    )
    assignment_date = fields.Date(string='Assignment Date', tracking=True)
    expected_return_date = fields.Date(string='Expected Return')

    # ── Financial ─────────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True
    )
    purchase_date = fields.Date(string='Purchase Date')
    purchase_price = fields.Monetary(
        string='Purchase Price', currency_field='currency_id', tracking=True
    )
    current_value = fields.Monetary(
        string='Current Book Value', currency_field='currency_id',
        compute='_compute_current_value', store=True
    )
    depreciation_rate = fields.Float(
        string='Depreciation Rate (%)',
        related='category_id.depreciation_rate', readonly=True
    )
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    age_years = fields.Float(
        string='Age (Years)', compute='_compute_age', store=True
    )

    # ── Purchase Integration ──────────────────────────────────────────────────
    po_line_id = fields.Many2one(
        'purchase.order.line', string='PO Line', copy=False
    )
    po_id = fields.Many2one(
        'purchase.order', string='Purchase Order',
        related='po_line_id.order_id', store=True, readonly=True
    )

    # ── Warranty & AMC ────────────────────────────────────────────────────────
    warranty_expiry_date = fields.Date(
        string='Warranty Expiry', tracking=True
    )
    warranty_status = fields.Selection([
        ('valid', 'Under Warranty'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Warranty Expired'),
        ('na', 'N/A'),
    ], string='Warranty Status', compute='_compute_warranty_status', store=True)
    amc_id = fields.Many2one(
        'it.amc', string='AMC Contract', tracking=True
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    assignment_ids = fields.One2many(
        'it.asset.assignment', 'asset_id', string='Assignment History'
    )
    software_ids = fields.Many2many(
        'it.software.license', 'it_asset_software_rel',
        'asset_id', 'license_id', string='Installed Software'
    )
    software_count = fields.Integer(compute='_compute_counts')
    maintenance_count = fields.Integer(compute='_compute_counts')
    request_count = fields.Integer(compute='_compute_counts')

    # ── Accounting ────────────────────────────────────────────────────────────
    move_ids = fields.One2many(
        'account.move', 'it_asset_id', string='GL Entries'
    )
    accounting_entry_count = fields.Integer(
        string='Journal Entries', compute='_compute_accounting_entry_count'
    )
    last_depreciation_date = fields.Date(
        string='Last Depreciation Posted', readonly=True, copy=False
    )
    accumulated_depreciation = fields.Monetary(
        string='Accumulated Depreciation Posted',
        currency_field='currency_id', readonly=True, copy=False, default=0.0
    )

    notes = fields.Text(string='Internal Notes')

    # ── SQL Constraints ───────────────────────────────────────────────────────
    # Odoo 19: models.Constraint replaces the removed _sql_constraints class attribute
    _asset_tag_uniq = models.Constraint(
        'UNIQUE(asset_tag)',
        'Asset Tag must be unique across all assets.',
    )

    # ── ORM Overrides ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('asset_tag'):
                vals['asset_tag'] = (
                    self.env['ir.sequence'].next_by_code('it.asset') or '/'
                )
            if not vals.get('barcode'):
                vals['barcode'] = vals['asset_tag']
        records = super().create(vals_list)
        records._generate_qr_codes()
        return records

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('warranty_expiry_date')
    def _compute_warranty_status(self):
        today = date.today()
        warn = int(
            self.env['ir.config_parameter'].sudo()
            .get_param('it_inventory.warranty_warning_days', 30)
        )
        for asset in self:
            exp = asset.warranty_expiry_date
            if not exp:
                asset.warranty_status = 'na'
            elif exp < today:
                asset.warranty_status = 'expired'
            elif exp <= today + timedelta(days=warn):
                asset.warranty_status = 'expiring'
            else:
                asset.warranty_status = 'valid'

    @api.depends('purchase_price', 'purchase_date', 'depreciation_rate')
    def _compute_current_value(self):
        today = date.today()
        for asset in self:
            if not asset.purchase_price or not asset.purchase_date:
                asset.current_value = asset.purchase_price or 0.0
                continue
            years = (today - asset.purchase_date).days / 365.25
            rate = (asset.depreciation_rate or 0.0) / 100
            asset.current_value = max(
                0.0, asset.purchase_price * ((1 - rate) ** years)
            )

    @api.depends('purchase_date')
    def _compute_age(self):
        today = date.today()
        for asset in self:
            if asset.purchase_date:
                asset.age_years = (today - asset.purchase_date).days / 365.25
            else:
                asset.age_years = 0.0

    def _compute_counts(self):
        Maintenance = self.env['maintenance.request']
        Request = self.env['it.asset.request']
        for asset in self:
            asset.software_count = len(asset.software_ids)
            asset.maintenance_count = Maintenance.search_count(
                [('it_asset_id', '=', asset.id)]
            )
            asset.request_count = Request.search_count(
                [('asset_id', '=', asset.id)]
            )

    def _compute_accounting_entry_count(self):
        for asset in self:
            asset.accounting_entry_count = self.env['account.move'].search_count(
                [('it_asset_id', '=', asset.id)]
            )

    # ── Accounting ───────────────────────────────────────────────────────────
    def _get_depreciation_journal(self):
        """Return the Miscellaneous journal for the asset's company."""
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id),
            ('name', 'not ilike', 'Exchange'),
            ('name', 'not ilike', 'Cash Basis'),
        ], limit=1)
        if not journal:
            raise UserError(_(
                "No 'General' type journal found for company '%s'. "
                "Please create one in Accounting ▸ Configuration ▸ Journals."
            ) % self.company_id.name)
        return journal

    def _compute_period_depreciation(self):
        """Annual depreciation amount using declining balance (same as current_value logic)."""
        if not self.purchase_price or not self.purchase_date:
            return 0.0
        rate = (self.depreciation_rate or 0.0) / 100.0
        if not rate:
            return 0.0
        book_value = self.current_value if self.current_value > 0 else self.purchase_price
        return round(book_value * rate, 2)

    def action_post_depreciation(self):
        """Post a depreciation journal entry for the current year's depreciation."""
        self.ensure_one()
        cat = self.category_id
        if not cat.account_depreciation_expense_id:
            raise UserError(_(
                "Please set a Depreciation Expense Account on category '%s'."
            ) % cat.name)
        if not cat.account_accumulated_depreciation_id and not cat.account_asset_id:
            raise UserError(_(
                "Please set an Accumulated Depreciation Account (or Asset Account) "
                "on category '%s'."
            ) % cat.name)

        amount = self._compute_period_depreciation()
        if amount <= 0:
            raise UserError(_("Depreciation amount is zero. Check the purchase price and rate."))

        credit_account = (
            cat.account_accumulated_depreciation_id or cat.account_asset_id
        )
        journal = self._get_depreciation_journal()
        today = date.today()

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': today,
            'ref': _('Depreciation — %s (%s)') % (self.name, self.asset_tag or ''),
            'company_id': self.company_id.id,
            'it_asset_id': self.id,
            'line_ids': [
                (0, 0, {
                    'account_id': cat.account_depreciation_expense_id.id,
                    'name': _('Depreciation — %s') % self.name,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': credit_account.id,
                    'name': _('Accumulated Depreciation — %s') % self.name,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        move._post()
        self.write({
            'last_depreciation_date': today,
            'accumulated_depreciation': self.accumulated_depreciation + amount,
        })
        self.message_post(
            body=_("Depreciation entry posted: %s %s (Journal Entry: %s)")
            % (self.currency_id.symbol, amount, move.name)
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_post_disposal_entry(self):
        """Post asset write-off journal entry on disposal."""
        self.ensure_one()
        cat = self.category_id
        if not cat.account_asset_id:
            raise UserError(_(
                "Please set an Asset Account on category '%s'."
            ) % cat.name)

        journal = self._get_depreciation_journal()
        today = date.today()

        original_cost = self.purchase_price or 0.0
        acc_dep = self.accumulated_depreciation or 0.0
        net_book_value = max(0.0, original_cost - acc_dep)

        line_ids = []
        # CR: Asset Account (remove original cost)
        if original_cost:
            line_ids.append((0, 0, {
                'account_id': cat.account_asset_id.id,
                'name': _('Asset disposal — %s') % self.name,
                'debit': 0.0,
                'credit': original_cost,
            }))
        # DR: Accumulated Depreciation (clear accumulated balance)
        if acc_dep and cat.account_accumulated_depreciation_id:
            line_ids.append((0, 0, {
                'account_id': cat.account_accumulated_depreciation_id.id,
                'name': _('Clear accumulated depreciation — %s') % self.name,
                'debit': acc_dep,
                'credit': 0.0,
            }))
        # DR: Loss on Disposal for net book value (if any residual)
        if net_book_value and cat.account_depreciation_expense_id:
            line_ids.append((0, 0, {
                'account_id': cat.account_depreciation_expense_id.id,
                'name': _('Loss on disposal — %s') % self.name,
                'debit': net_book_value,
                'credit': 0.0,
            }))

        if not line_ids:
            raise UserError(_("No accounting configuration found. Set Asset Account on category."))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': today,
            'ref': _('Asset Disposal — %s (%s)') % (self.name, self.asset_tag or ''),
            'company_id': self.company_id.id,
            'it_asset_id': self.id,
            'line_ids': line_ids,
        })
        move._post()
        self.message_post(
            body=_("Disposal entry posted — Net Book Value: %s %s (Journal Entry: %s)")
            % (self.currency_id.symbol, net_book_value, move.name)
        )

    def action_view_journal_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('it_asset_id', '=', self.id)],
            'context': {'default_it_asset_id': self.id},
        }

    # ── QR Code ───────────────────────────────────────────────────────────────
    def _generate_qr_codes(self):
        for asset in self:
            data = (
                f"IT-ASSET\n"
                f"Tag:{asset.asset_tag}\n"
                f"Name:{asset.name}\n"
                f"Serial:{asset.serial_number or ''}"
            )
            if _HAS_QRCODE:
                qr = qrcode.QRCode(version=1, box_size=8, border=4)
                qr.add_data(data)
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                buf = BytesIO()
                img.save(buf, format='PNG')
                asset.qr_code = base64.b64encode(buf.getvalue())
            else:
                asset.qr_code = _make_qr_png_fallback(data)

    def action_regenerate_qr(self):
        self._generate_qr_codes()

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and not self.department_id:
            self.department_id = self.employee_id.department_id

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id and self.category_id.default_warranty_months and self.purchase_date:
            from dateutil.relativedelta import relativedelta
            self.warranty_expiry_date = (
                self.purchase_date
                + relativedelta(months=self.category_id.default_warranty_months)
            )

    # ── State Transitions ─────────────────────────────────────────────────────
    def action_confirm(self):
        for asset in self:
            if asset.state != 'draft':
                raise UserError(_("Only draft assets can be confirmed."))
            asset.write({'state': 'in_stock'})
            asset.message_post(body=_("Asset confirmed and moved to In Stock."))

    def action_assign(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Asset'),
            'res_model': 'it.asset.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_ids': [(6, 0, self.ids)]},
        }

    def action_return(self):
        self.ensure_one()
        if self.state != 'assigned':
            raise UserError(_("Only assigned assets can be returned."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Asset'),
            'res_model': 'it.asset.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }

    def action_set_under_repair(self):
        for asset in self:
            if asset.state not in ('in_stock', 'assigned', 'returned', 'damaged'):
                raise UserError(
                    _("Asset '%s' cannot be sent for repair from its current state.")
                    % asset.name
                )
            asset.write({'state': 'under_repair'})
            asset.message_post(body=_("Asset sent for repair."))

    def action_repair_done(self):
        for asset in self:
            if asset.state != 'under_repair':
                raise UserError(_("Only assets under repair can be marked as repaired."))
            new_state = 'assigned' if asset.employee_id else 'in_stock'
            asset.write({'state': new_state})
            asset.message_post(body=_("Repair completed. Asset returned to %s.") % new_state)

    def action_set_lost(self):
        for asset in self:
            asset.write({
                'state': 'lost',
                'employee_id': False,
            })
            asset.message_post(body=_("Asset reported as LOST."))

    def action_set_damaged(self):
        for asset in self:
            asset.write({'state': 'damaged'})
            asset.message_post(body=_("Asset reported as DAMAGED."))

    def action_retire(self):
        for asset in self:
            asset.write({
                'state': 'retired',
                'employee_id': False,
            })
            asset.message_post(body=_("Asset retired."))

    def action_dispose(self):
        for asset in self:
            if asset.state != 'retired':
                raise UserError(_("Only retired assets can be disposed."))
            asset.write({'state': 'disposed'})
            asset.active = False
            asset.message_post(body=_("Asset disposed and archived."))
            if asset.category_id.account_asset_id:
                try:
                    asset.action_post_disposal_entry()
                except Exception:
                    pass  # accounting not configured — dispose silently

    def action_reset_to_stock(self):
        for asset in self:
            asset.write({'state': 'in_stock', 'employee_id': False, 'department_id': False})
            asset.message_post(body=_("Asset returned to In Stock."))

    # ── Smart Button Actions ──────────────────────────────────────────────────
    def action_view_maintenance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Requests'),
            'res_model': 'maintenance.request',
            'view_mode': 'list,form',
            'domain': [('it_asset_id', '=', self.id)],
            'context': {'default_it_asset_id': self.id},
        }

    def action_view_software(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Software Licenses'),
            'res_model': 'it.software.license',
            'view_mode': 'list,form',
            'domain': [('asset_ids', 'in', self.id)],
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset Requests'),
            'res_model': 'it.asset.request',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
        }

    # ── Scheduled Actions ─────────────────────────────────────────────────────
    @api.model
    def cron_send_warranty_alerts(self):
        warn_days = int(
            self.env['ir.config_parameter'].sudo()
            .get_param('it_inventory.warranty_warning_days', 30)
        )
        today = date.today()
        threshold = today + timedelta(days=warn_days)
        expiring = self.search([
            ('warranty_expiry_date', '>=', today.isoformat()),
            ('warranty_expiry_date', '<=', threshold.isoformat()),
            ('state', 'not in', ['retired', 'disposed', 'lost']),
        ])
        template = self.env.ref(
            'it_inventory.email_template_warranty_expiry',
            raise_if_not_found=False
        )
        if template:
            for asset in expiring:
                template.send_mail(asset.id, force_send=False)

    @api.model
    def cron_update_depreciation(self):
        assets = self.search([
            ('state', 'not in', ['retired', 'disposed']),
            ('purchase_price', '>', 0),
            ('purchase_date', '!=', False),
        ])
        for asset in assets:
            asset._compute_current_value()

    @api.model
    def cron_update_warranty_status(self):
        self.search([])._compute_warranty_status()
