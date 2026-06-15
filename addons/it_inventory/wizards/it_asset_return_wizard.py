from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ItAssetReturnWizard(models.TransientModel):
    _name = 'it.asset.return.wizard'
    _description = 'Asset Return Wizard'

    asset_id = fields.Many2one(
        'it.asset', string='Asset', required=True,
        domain="[('state', '=', 'assigned')]"
    )
    employee_id = fields.Many2one(
        'hr.employee', related='asset_id.employee_id',
        string='Returned By (Employee)', readonly=True
    )
    return_date = fields.Date(
        string='Return Date', required=True, default=fields.Date.today
    )
    condition_on_return = fields.Selection([
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
    ], string='Condition on Return', required=True, default='good')
    next_state = fields.Selection([
        ('in_stock', 'Return to Stock'),
        ('under_repair', 'Send to Repair'),
        ('retired', 'Retire Asset'),
    ], string='Next State', required=True, default='in_stock')
    notes = fields.Text(string='Return Notes / Remarks')

    def action_return(self):
        self.ensure_one()
        asset = self.asset_id
        if asset.state != 'assigned':
            raise UserError(_("This asset is not currently assigned."))

        # Close active assignment
        active = self.env['it.asset.assignment'].search([
            ('asset_id', '=', asset.id),
            ('state', '=', 'active'),
        ])
        active.write({
            'state': 'returned',
            'returned_date': self.return_date,
            'returned_by': self.env.user.id,
            'condition_on_return': self.condition_on_return,
            'notes': (active.notes or '') + (
                f'\n[Return] {self.notes}' if self.notes else ''
            ),
        })

        # Determine new asset state
        new_state = self.next_state
        if self.condition_on_return == 'lost':
            new_state = 'lost'
        elif self.condition_on_return == 'damaged' and self.next_state == 'in_stock':
            new_state = 'damaged'

        vals = {
            'state': new_state,
            'employee_id': False,
            'assignment_date': False,
            'expected_return_date': False,
        }
        # Keep department only if going to repair (context)
        if new_state not in ('under_repair',):
            vals['department_id'] = False

        asset.write(vals)
        asset.message_post(
            body=_("Returned by <b>%s</b> on %s. Condition: %s. Next: %s.") % (
                active.employee_id.name if active else '—',
                self.return_date,
                dict(self._fields['condition_on_return'].selection).get(
                    self.condition_on_return, ''
                ),
                dict(self._fields['next_state'].selection).get(self.next_state, ''),
            )
        )
        return {'type': 'ir.actions.act_window_close'}
