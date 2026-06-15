from odoo import api, fields, models, _


class ItAssetAssignment(models.Model):
    _name = 'it.asset.assignment'
    _description = 'IT Asset Assignment History'
    _order = 'assigned_date desc'

    asset_id = fields.Many2one(
        'it.asset', string='Asset', required=True, ondelete='cascade', index=True
    )
    asset_tag = fields.Char(related='asset_id.asset_tag', store=True, readonly=True)
    category_id = fields.Many2one(
        related='asset_id.category_id', store=True, readonly=True
    )

    employee_id = fields.Many2one(
        'hr.employee', string='Assigned To', required=True, ondelete='restrict'
    )
    department_id = fields.Many2one('hr.department', string='Department')
    location_id = fields.Many2one('it.asset.location', string='Location')

    assigned_by = fields.Many2one(
        'res.users', string='Assigned By',
        default=lambda self: self.env.user, readonly=True
    )
    assigned_date = fields.Date(
        string='Assigned Date', required=True, default=fields.Date.today
    )
    expected_return_date = fields.Date(string='Expected Return')
    returned_date = fields.Date(string='Returned Date')
    returned_by = fields.Many2one('res.users', string='Returned By')

    purpose = fields.Text(string='Purpose / Reason')
    notes = fields.Text(string='Notes')

    state = fields.Selection([
        ('active', 'Active'),
        ('returned', 'Returned'),
    ], string='Status', default='active', required=True, index=True)

    condition_on_assign = fields.Selection([
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition on Assignment', default='good')

    condition_on_return = fields.Selection([
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
    ], string='Condition on Return')

    duration_days = fields.Integer(
        string='Duration (Days)', compute='_compute_duration', store=True
    )

    @api.depends('assigned_date', 'returned_date')
    def _compute_duration(self):
        today = fields.Date.today()
        for rec in self:
            end = rec.returned_date or today
            if rec.assigned_date:
                rec.duration_days = (end - rec.assigned_date).days
            else:
                rec.duration_days = 0

    def action_return(self):
        for rec in self:
            rec.write({
                'state': 'returned',
                'returned_date': fields.Date.today(),
                'returned_by': self.env.user.id,
            })
