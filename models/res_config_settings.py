# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_cpe_summary_url_lycet = fields.Char('URL LYCET', related='company_id.l10n_pe_cpe_summary_url_lycet', readonly=False)
    l10n_pe_cpe_summary_url_lycet_token = fields.Char('Token LYCET', related='company_id.l10n_pe_cpe_summary_url_lycet_token', readonly=False)
    l10n_pe_cpe_summary_journal_ids = fields.Many2many('account.journal', string='Diarios para resumen de boletas', related='company_id.l10n_pe_cpe_summary_journal_ids', readonly=False,
        help='Diarios que se considerarán para la generación del resumen de boletas mediante cron.')