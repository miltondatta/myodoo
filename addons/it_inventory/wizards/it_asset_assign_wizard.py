from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ItAssetAssignWizard(models.TransientModel):
    _name = 'it.asset.assign.wizard'
    _description = 'Asset Assignment Wizard'

    asset_ids = fields.Many2many(
        'it.asset', string='Assets to Assign',
        domain="[('state', 'in', ['in_stock', 'reserved', 'returned'])]"
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Assign To', required=True,
        domain="[('active', '=', True)]"
    )
    department_id = fields.Many2one('hr.department', string='Department')
    location_id = fields.Many2one('it.asset.location', string='Delivery Location')
    assignment_date = fields.Date(
        string='Assignment Date', required=True, default=fields.Date.today
    )
    expected_return_date = fields.Date(string='Expected Return Date')
    purpose = fields.Text(string='Purpose / Justification')
    notes = fields.Text(string='Handover Notes')
    condition_on_assign = fields.Selection([
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition', default='good', required=True)
    # For fulfilling a request
    request_id = fields.Many2one('it.asset.request', string='Fulfils Request')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id

    def action_assign(self):
        if not self.asset_ids:
            raise UserError(_("Please select at least one asset."))

        for asset in self.asset_ids:
            if asset.state not in ('in_stock', 'reserved', 'returned'):
                raise UserError(
                    _("Asset '%s' (state: %s) is not available for assignment.")
                    % (asset.name, asset.state)
                )
            # Close any active assignment for this asset
            active_assignments = self.env['it.asset.assignment'].search([
                ('asset_id', '=', asset.id),
                ('state', '=', 'active'),
            ])
            active_assignments.write({
                'state': 'returned',
                'returned_date': self.assignment_date,
                'returned_by': self.env.user.id,
            })

            # Create new assignment record
            self.env['it.asset.assignment'].create({
                'asset_id': asset.id,
                'employee_id': self.employee_id.id,
                'department_id': self.department_id.id,
                'location_id': self.location_id.id if self.location_id else False,
                'assigned_date': self.assignment_date,
                'expected_return_date': self.expected_return_date,
                'assigned_by': self.env.user.id,
                'purpose': self.purpose,
                'notes': self.notes,
                'condition_on_assign': self.condition_on_assign,
                'state': 'active',
            })

            asset.write({
                'state': 'assigned',
                'employee_id': self.employee_id.id,
                'department_id': self.department_id.id,
                'location_id': self.location_id.id if self.location_id else asset.location_id.id,
                'assignment_date': self.assignment_date,
                'expected_return_date': self.expected_return_date,
            })
            asset.message_post(
                body=_("Assigned to <b>%s</b> (%s) on %s%s.") % (
                    self.employee_id.name,
                    self.department_id.name if self.department_id else '—',
                    self.assignment_date,
                    f' — {self.purpose}' if self.purpose else '',
                )
            )

        if self.request_id and self.request_id.state == 'approved':
            self.request_id.write({'state': 'fulfilled'})
            self.request_id.message_post(
                body=_("Request fulfilled with asset(s): %s")
                % ', '.join(self.asset_ids.mapped('asset_tag'))
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Assets Assigned'),
                'message': _('%d asset(s) assigned to %s.')
                           % (len(self.asset_ids), self.employee_id.name),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
