from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ItAssetRequest(models.Model):
    _name = 'it.asset.request'
    _description = 'IT Asset Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc'

    name = fields.Char(
        string='Request Reference', copy=False,
        default='New', readonly=True, tracking=True
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Requested By',
        required=True, tracking=True,
        default=lambda self: self.env.user.employee_id
    )
    department_id = fields.Many2one(
        'hr.department', string='Department',
        related='employee_id.department_id', store=True, readonly=False, tracking=True
    )
    category_id = fields.Many2one(
        'it.asset.category', string='Asset Category Requested',
        required=True, tracking=True
    )
    asset_id = fields.Many2one(
        'it.asset', string='Assigned Asset', tracking=True, copy=False
    )

    request_date = fields.Date(
        string='Request Date', default=fields.Date.today, required=True
    )
    required_by_date = fields.Date(string='Required By', tracking=True)
    purpose = fields.Text(string='Business Justification', required=True)
    notes = fields.Text(string='Additional Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, index=True)

    approved_by = fields.Many2one(
        'res.users', string='Approved By', readonly=True, copy=False
    )
    approved_date = fields.Datetime(
        string='Approved On', readonly=True, copy=False
    )
    rejection_reason = fields.Text(string='Rejection Reason')

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
        ('2', 'Critical'),
    ], string='Priority', default='0', tracking=True)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('it.asset.request') or 'New'
                )
        return super().create(vals_list)

    def action_submit(self):
        for req in self:
            if req.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            req.write({'state': 'submitted'})
            req.message_post(body=_("Request submitted for approval."))
            req.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=req._get_approver().id,
                note=_("Please review IT asset request %s from %s.") % (
                    req.name, req.employee_id.name
                ),
            )

    def action_approve(self):
        for req in self:
            if req.state != 'submitted':
                raise UserError(_("Only submitted requests can be approved."))
            req.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            req.message_post(body=_("Request approved by %s.") % self.env.user.name)

    def action_reject(self):
        for req in self:
            req.write({'state': 'rejected'})
            req.message_post(
                body=_("Request rejected. Reason: %s") % (req.rejection_reason or 'N/A')
            )

    def action_fulfil(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Only approved requests can be fulfilled."))
        if not self.asset_id:
            raise UserError(_("Please link an asset to fulfil this request."))
        if self.asset_id.state not in ('in_stock', 'reserved', 'returned'):
            raise UserError(
                _("Asset '%s' is not available for assignment.") % self.asset_id.name
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assign Asset'),
            'res_model': 'it.asset.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_ids': [(6, 0, [self.asset_id.id])],
                'default_employee_id': self.employee_id.id,
                'default_request_id': self.id,
            },
        }

    def action_cancel(self):
        for req in self:
            req.write({'state': 'cancelled'})

    def _get_approver(self):
        group = self.env.ref(
            'it_inventory.group_it_manager', raise_if_not_found=False
        )
        if group and group.user_ids:
            return group.user_ids[0]
        return self.env.user
