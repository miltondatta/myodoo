from odoo import api, fields, models, _


class StockPicking(models.Model):
    """Auto-create IT assets when products linked to IT categories are received."""
    _inherit = 'stock.picking'

    it_assets_created = fields.Boolean(
        string='IT Assets Created', readonly=True, copy=False
    )

    def button_validate(self):
        result = super().button_validate()
        self._auto_create_it_assets()
        return result

    def _auto_create_it_assets(self):
        """For each received product move, if the product category maps to an
        IT asset category, create a draft IT asset."""
        for picking in self:
            if picking.picking_type_id.code != 'incoming':
                continue
            if picking.it_assets_created:
                continue

            assets_to_create = []
            for move in picking.move_ids.filtered(
                lambda m: m.state == 'done' and m.product_id
            ):
                product = move.product_id
                it_category = self.env['it.asset.category'].search([
                    ('product_category_id', '=', product.categ_id.id)
                ], limit=1)
                if not it_category:
                    continue

                po_line = move.purchase_line_id
                qty = int(move.quantity)
                for _ in range(max(1, qty)):
                    assets_to_create.append({
                        'name': product.display_name,
                        'category_id': it_category.id,
                        'brand': product.description_sale or '',
                        'purchase_date': picking.scheduled_date
                            and picking.scheduled_date.date(),
                        'purchase_price': po_line.price_unit if po_line else 0.0,
                        'vendor_id': picking.partner_id.id,
                        'po_line_id': po_line.id if po_line else False,
                        'state': 'in_stock',
                    })

            if assets_to_create:
                created = self.env['it.asset'].create(assets_to_create)
                picking.it_assets_created = True
                picking.message_post(
                    body=_("%d IT asset(s) auto-created from this receipt: %s")
                    % (len(created), ', '.join(created.mapped('asset_tag')))
                )


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    it_asset_ids = fields.One2many(
        'it.asset', 'po_line_id', string='IT Assets Created'
    )
    it_asset_count = fields.Integer(
        string='Assets', compute='_compute_it_asset_count'
    )

    def _compute_it_asset_count(self):
        for line in self:
            line.it_asset_count = len(line.it_asset_ids)
