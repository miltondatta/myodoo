from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ItAssetAudit(models.Model):
    _name = 'it.asset.audit'
    _description = 'IT Asset Audit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'audit_date desc'

    name = fields.Char(
        string='Audit Reference', copy=False,
        default='New', readonly=True, tracking=True
    )
    audit_date = fields.Date(
        string='Audit Date', required=True, default=fields.Date.today
    )
    planned_end_date = fields.Date(string='Planned End Date')
    actual_end_date = fields.Date(string='Actual End Date', readonly=True)

    auditor_id = fields.Many2one(
        'res.users', string='Lead Auditor',
        required=True, default=lambda self: self.env.user
    )
    auditor_ids = fields.Many2many(
        'res.users', 'it_audit_auditor_rel', 'audit_id', 'user_id',
        string='Audit Team'
    )

    scope = fields.Selection([
        ('all', 'All Active Assets'),
        ('department', 'By Department'),
        ('location', 'By Location'),
        ('category', 'By Category'),
    ], string='Audit Scope', required=True, default='all')
    department_id = fields.Many2one('hr.department', string='Department')
    location_id = fields.Many2one('it.asset.location', string='Location')
    category_id = fields.Many2one('it.asset.category', string='Category')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    audit_line_ids = fields.One2many(
        'it.asset.audit.line', 'audit_id', string='Audit Lines'
    )

    total_assets = fields.Integer(compute='_compute_stats', store=True)
    verified_count = fields.Integer(compute='_compute_stats', store=True)
    missing_count = fields.Integer(compute='_compute_stats', store=True)
    damaged_count = fields.Integer(compute='_compute_stats', store=True)
    pending_count = fields.Integer(compute='_compute_stats', store=True)
    completion_rate = fields.Float(compute='_compute_stats', store=True)

    notes = fields.Text(string='Notes / Findings')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('it.asset.audit') or 'New'
                )
        return super().create(vals_list)

    @api.depends('audit_line_ids.condition')
    def _compute_stats(self):
        for audit in self:
            lines = audit.audit_line_ids
            audit.total_assets = len(lines)
            audit.pending_count = len(lines.filtered(lambda l: l.condition == 'pending'))
            audit.verified_count = len(lines.filtered(lambda l: l.condition == 'good'))
            audit.missing_count = len(lines.filtered(lambda l: l.condition == 'missing'))
            audit.damaged_count = len(lines.filtered(lambda l: l.condition == 'damaged'))
            total = audit.total_assets
            audit.completion_rate = (
                ((total - audit.pending_count) / total * 100) if total else 0.0
            )

    def action_generate_lines(self):
        """Build audit lines from current asset state based on scope."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Lines can only be generated for draft audits."))

        domain = [('state', 'not in', ['retired', 'disposed', 'draft'])]
        if self.scope == 'department':
            if not self.department_id:
                raise UserError(_("Please select a department."))
            domain.append(('department_id', '=', self.department_id.id))
        elif self.scope == 'location':
            if not self.location_id:
                raise UserError(_("Please select a location."))
            domain.append(('location_id', '=', self.location_id.id))
        elif self.scope == 'category':
            if not self.category_id:
                raise UserError(_("Please select a category."))
            domain.append(('category_id', '=', self.category_id.id))

        assets = self.env['it.asset'].search(domain)
        if not assets:
            raise UserError(_("No assets found matching the audit scope."))

        self.audit_line_ids.unlink()
        lines = [
            {
                'audit_id': self.id,
                'asset_id': a.id,
                'expected_employee_id': a.employee_id.id,
                'expected_location_id': a.location_id.id,
                'condition': 'pending',
            }
            for a in assets
        ]
        self.env['it.asset.audit.line'].create(lines)
        self.write({'state': 'in_progress'})
        self.message_post(
            body=_("Audit started. %d assets in scope.") % len(assets)
        )

    def action_complete(self):
        self.ensure_one()
        pending = self.audit_line_ids.filtered(lambda l: l.condition == 'pending')
        if pending:
            raise UserError(
                _("%d assets are still pending verification. "
                  "Please verify all assets or mark them as missing.") % len(pending)
            )
        for line in self.audit_line_ids:
            if line.condition == 'missing':
                line.asset_id.write({'state': 'lost'})
                line.asset_id.message_post(
                    body=_("Marked lost during audit %s.") % self.name
                )
            elif line.condition == 'damaged':
                line.asset_id.write({'state': 'damaged'})
                line.asset_id.message_post(
                    body=_("Marked damaged during audit %s.") % self.name
                )
        self.write({
            'state': 'completed',
            'actual_end_date': fields.Date.today(),
        })
        self.message_post(
            body=_(
                "Audit completed. Found: %d | Missing: %d | Damaged: %d"
            ) % (self.verified_count, self.missing_count, self.damaged_count)
        )

    def action_cancel(self):
        for audit in self:
            audit.write({'state': 'cancelled'})


class ItAssetAuditLine(models.Model):
    _name = 'it.asset.audit.line'
    _description = 'IT Asset Audit Line'
    _order = 'audit_id, asset_id'

    audit_id = fields.Many2one(
        'it.asset.audit', string='Audit', ondelete='cascade', required=True
    )
    asset_id = fields.Many2one(
        'it.asset', string='Asset', required=True, ondelete='restrict'
    )
    asset_tag = fields.Char(related='asset_id.asset_tag', readonly=True, store=True)
    serial_number = fields.Char(related='asset_id.serial_number', readonly=True)
    category_id = fields.Many2one(related='asset_id.category_id', readonly=True, store=True)

    expected_employee_id = fields.Many2one('hr.employee', string='Expected With')
    found_employee_id = fields.Many2one('hr.employee', string='Actually Found With')
    expected_location_id = fields.Many2one('it.asset.location', string='Expected Location')
    found_location_id = fields.Many2one('it.asset.location', string='Found At Location')

    condition = fields.Selection([
        ('pending', 'Pending'),
        ('good', 'Good — Verified'),
        ('damaged', 'Damaged'),
        ('missing', 'Missing'),
    ], string='Condition', required=True, default='pending')

    remarks = fields.Text(string='Remarks')
    verified_by = fields.Many2one('res.users', string='Verified By')
    verified_date = fields.Datetime(string='Verified On')

    def action_mark_good(self):
        self.write({
            'condition': 'good',
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
        })

    def action_mark_damaged(self):
        self.write({
            'condition': 'damaged',
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
        })

    def action_mark_missing(self):
        self.write({
            'condition': 'missing',
            'verified_by': self.env.user.id,
            'verified_date': fields.Datetime.now(),
        })
