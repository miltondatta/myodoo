from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ItTicket(models.Model):
    """Internal IT support ticket — CE replacement for Enterprise Helpdesk."""
    _name = 'it.ticket'
    _description = 'IT Support Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, create_date desc'

    name = fields.Char(
        string='Subject', required=True, tracking=True
    )
    reference = fields.Char(
        string='Ticket Ref', copy=False, readonly=True, default='New'
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Reported By', required=True,
        default=lambda self: self.env.user.employee_id
    )
    department_id = fields.Many2one(
        'hr.department', string='Department',
        related='employee_id.department_id', store=True
    )
    asset_id = fields.Many2one(
        'it.asset', string='Affected Asset', tracking=True
    )
    category = fields.Selection([
        ('hardware', 'Hardware Issue'),
        ('software', 'Software Issue'),
        ('network', 'Network / Connectivity'),
        ('access', 'Access / Permissions'),
        ('email', 'Email'),
        ('printing', 'Printing'),
        ('new_request', 'New Equipment Request'),
        ('other', 'Other'),
    ], string='Issue Category', required=True, default='hardware', tracking=True)

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Critical'),
    ], string='Priority', default='1', tracking=True)

    description = fields.Html(string='Issue Description')
    resolution = fields.Html(string='Resolution / Notes')

    assigned_to = fields.Many2one(
        'res.users', string='Assigned IT Staff', tracking=True
    )

    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending User'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', tracking=True, index=True)

    open_date = fields.Datetime(
        string='Opened On', default=fields.Datetime.now, readonly=True
    )
    resolved_date = fields.Datetime(string='Resolved On', readonly=True)
    closed_date = fields.Datetime(string='Closed On', readonly=True)
    sla_deadline = fields.Datetime(string='SLA Deadline', compute='_compute_sla', store=True)

    resolution_time_hours = fields.Float(
        string='Resolution Time (hrs)', compute='_compute_resolution_time', store=True
    )

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('it.ticket') or 'New'
                )
        return super().create(vals_list)

    @api.depends('priority', 'open_date')
    def _compute_sla(self):
        from datetime import timedelta
        sla_hours = {'0': 72, '1': 24, '2': 8, '3': 2}
        for ticket in self:
            if ticket.open_date and ticket.priority:
                hours = sla_hours.get(ticket.priority, 24)
                ticket.sla_deadline = ticket.open_date + timedelta(hours=hours)
            else:
                ticket.sla_deadline = False

    @api.depends('open_date', 'resolved_date')
    def _compute_resolution_time(self):
        for ticket in self:
            if ticket.open_date and ticket.resolved_date:
                delta = ticket.resolved_date - ticket.open_date
                ticket.resolution_time_hours = delta.total_seconds() / 3600
            else:
                ticket.resolution_time_hours = 0.0

    def action_start(self):
        for t in self:
            t.write({'state': 'in_progress', 'assigned_to': self.env.user.id})

    def action_resolve(self):
        for t in self:
            if not t.resolution:
                raise UserError(_("Please enter a resolution before marking as resolved."))
            t.write({
                'state': 'resolved',
                'resolved_date': fields.Datetime.now(),
            })
            t.message_post(body=_("Ticket resolved."))

    def action_close(self):
        for t in self:
            t.write({
                'state': 'closed',
                'closed_date': fields.Datetime.now(),
            })

    def action_reopen(self):
        for t in self:
            t.write({'state': 'in_progress', 'resolved_date': False})

    def action_cancel(self):
        for t in self:
            t.write({'state': 'cancelled'})
