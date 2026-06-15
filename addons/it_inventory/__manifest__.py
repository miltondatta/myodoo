{
    'name': 'IT Inventory',
    'version': '19.0.1.0.0',
    'summary': 'Manage IT assets, devices, and equipment inventory',
    'description': """
        IT Inventory Management
        =======================
        Track and manage all IT assets including:
        - Computers, laptops, and servers
        - Networking equipment
        - Peripherals and accessories
        - Software licenses
        - Assignment to employees or departments
    """,
    'author': 'Milton',
    'website': 'https://www.pentabd.com',
    'category': 'Technical',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/it_asset_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
