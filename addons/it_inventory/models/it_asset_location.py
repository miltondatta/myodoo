from odoo import fields, models


class ItAssetLocation(models.Model):
    _name = 'it.asset.location'
    _description = 'IT Asset Location'
    _order = 'complete_name'
    _parent_name = 'parent_id'
    _parent_store = True

    name = fields.Char(string='Location Name', required=True)
    parent_id = fields.Many2one(
        'it.asset.location', string='Parent Location',
        ondelete='restrict', index=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('it.asset.location', 'parent_id', string='Sub-locations')
    complete_name = fields.Char(
        string='Full Path', compute='_compute_complete_name', store=True, recursive=True
    )

    building = fields.Char(string='Building')
    floor = fields.Char(string='Floor / Level')
    room = fields.Char(string='Room / Area')
    description = fields.Text(string='Description')

    # Link to stock location for inventory integration
    stock_location_id = fields.Many2one(
        'stock.location', string='Warehouse Location',
        domain="[('usage', '=', 'internal')]",
        help='Map this IT location to a stock location for inventory sync.'
    )

    asset_count = fields.Integer(string='Assets', compute='_compute_asset_count')
    active = fields.Boolean(default=True)

    def _compute_complete_name(self):
        for loc in self:
            if loc.parent_id:
                loc.complete_name = f'{loc.parent_id.complete_name} / {loc.name}'
            else:
                loc.complete_name = loc.name

    def _compute_asset_count(self):
        data = self.env['it.asset'].read_group(
            [('location_id', 'in', self.ids)],
            ['location_id'], ['location_id']
        )
        mapping = {d['location_id'][0]: d['location_id_count'] for d in data}
        for loc in self:
            loc.asset_count = mapping.get(loc.id, 0)

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Assets at {self.complete_name}',
            'res_model': 'it.asset',
            'view_mode': 'list,kanban,form',
            'domain': [('location_id', '=', self.id)],
            'context': {'default_location_id': self.id},
        }
