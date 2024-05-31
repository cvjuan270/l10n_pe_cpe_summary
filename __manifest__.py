# -*- coding: utf-8 -*-
{
    'name': 'L10n_pe_cpe_summary',
    'version': '',
    'description': """ L10n_pe_cpe_summary Description """,
    'summary': """ L10n_pe_cpe_summary Summary """,
    'author': '',
    'website': '',
    'category': '',
    'depends': ['base', 'account', 'l10n_pe'],
    "data": [
        "views/l10n_pe_cpe_summary_views.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml"
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
