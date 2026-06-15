from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    it_asset_ids = fields.One2many(
        'it.asset', 'employee_id', string='Assigned IT Assets'
    )
    # Computed (non-stored) — never adds columns to hr_employee table,
    # avoiding race-condition errors during --update before schema migration.
    it_asset_count = fields.Integer(
        string='IT Assets', compute='_compute_it_asset_count'
    )
    it_ticket_count = fields.Integer(
        string='IT Tickets', compute='_compute_it_asset_count'
    )

    def _compute_it_asset_count(self):
        Asset = self.env['it.asset']
        Ticket = self.env['it.ticket']
        for emp in self:
            emp.it_asset_count = Asset.search_count([
                ('employee_id', '=', emp.id),
                ('state', '=', 'assigned'),
            ])
            emp.it_ticket_count = Ticket.search_count([
                ('employee_id', '=', emp.id)
            ])

    def action_view_it_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s — IT Assets') % self.name,
            'res_model': 'it.asset',
            'view_mode': 'list,kanban,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_view_it_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('%s — IT Tickets') % self.name,
            'res_model': 'it.ticket',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_it_onboarding(self):
        """Launch onboarding checklist for new employee."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('IT Onboarding — %s') % self.name,
            'res_model': 'it.asset.request',
            'view_mode': 'form',
            'context': {
                'default_employee_id': self.id,
                'default_purpose': _('IT Onboarding — New Employee Setup'),
            },
        }

    def action_it_offboarding(self):
        """Show all assets to be returned for offboarding."""
        self.ensure_one()
        assigned_assets = self.env['it.asset'].search([
            ('employee_id', '=', self.id),
            ('state', '=', 'assigned'),
        ])
        if not assigned_assets:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Assets'),
                    'message': _('%s has no assets to return.') % self.name,
                    'type': 'info',
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('IT Offboarding — Assets to Return'),
            'res_model': 'it.asset',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id), ('state', '=', 'assigned')],
        }
