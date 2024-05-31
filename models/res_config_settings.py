# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_cpe_summary_url_lycet = fields.Char('URL LYCET', related='company_id.l10n_pe_cpe_summary_url_lycet', readonly=False)
    l10n_pe_cpe_summary_url_lycet_token = fields.Char('Token LYCET', related='company_id.l10n_pe_cpe_summary_url_lycet_token', readonly=False)