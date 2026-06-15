from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    it_asset_id = fields.Many2one(
        'it.asset', string='IT Asset',
        ondelete='set null', index=True, copy=False,
        help='IT Asset that generated this journal entry.'
    )
