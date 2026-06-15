from odoo import fields, models


class ItAssetCategory(models.Model):
    _name = 'it.asset.category'
    _description = 'IT Asset Category'
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True

    name = fields.Char(string='Category Name', required=True, translate=True)
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        'it.asset.category', string='Parent Category',
        ondelete='restrict', index=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('it.asset.category', 'parent_id', string='Sub-categories')
    complete_name = fields.Char(
        string='Full Path', compute='_compute_complete_name', store=True, recursive=True
    )
    asset_type = fields.Selection([
        ('computer', 'Computer / Desktop'),
        ('laptop', 'Laptop'),
        ('server', 'Server'),
        ('networking', 'Networking Equipment'),
        ('mobile', 'Mobile / Tablet'),
        ('printer', 'Printer / Scanner'),
        ('storage', 'Storage Device'),
        ('peripheral', 'Peripheral / Accessory'),
        ('display', 'Monitor / Display'),
        ('software', 'Software License'),
        ('telecom', 'Telephone / VOIP'),
        ('other', 'Other'),
    ], string='Asset Type', required=True, default='computer')

    # Depreciation
    depreciation_rate = fields.Float(
        string='Annual Depreciation Rate (%)',
        default=20.0,
        help='Percentage of value lost per year (declining balance method).'
    )
    useful_life_years = fields.Integer(
        string='Useful Life (Years)', default=3
    )

    # Accounting
    account_asset_id = fields.Many2one(
        'account.account', string='Asset Account',
        domain="[('account_type', 'in', ['asset_fixed', 'asset_non_current'])]",
        help='GL account debited when asset is capitalised.'
    )
    account_accumulated_depreciation_id = fields.Many2one(
        'account.account', string='Accumulated Depreciation Account',
        domain="[('account_type', 'in', ['asset_fixed', 'asset_non_current'])]",
        help='Contra-asset account credited for periodic depreciation (usually a sub-account of the asset account).'
    )
    account_depreciation_expense_id = fields.Many2one(
        'account.account', string='Depreciation Expense Account',
        domain="[('account_type', 'in', ['expense', 'expense_depreciation'])]",
        help='P&L account debited for each depreciation entry.'
    )

    # Purchase integration
    product_category_id = fields.Many2one(
        'product.category', string='Linked Product Category',
        help='When a PO receipt includes products in this category, assets are auto-created.'
    )

    # Defaults
    default_warranty_months = fields.Integer(
        string='Default Warranty (Months)', default=12
    )

    asset_count = fields.Integer(
        string='Assets', compute='_compute_asset_count'
    )

    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = f'{category.parent_id.complete_name} / {category.name}'
            else:
                category.complete_name = category.name

    def _compute_asset_count(self):
        data = self.env['it.asset'].read_group(
            [('category_id', 'in', self.ids)],
            ['category_id'], ['category_id']
        )
        mapping = {d['category_id'][0]: d['category_id_count'] for d in data}
        for cat in self:
            cat.asset_count = mapping.get(cat.id, 0)

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Assets — {self.name}',
            'res_model': 'it.asset',
            'view_mode': 'list,kanban,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }
