# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResCampany(models.Model):
    _inherit = 'res.company'

    l10n_pe_cpe_summary_url_lycet = fields.Char('URL LYCET', required=True, default='https://lycet.tagre.pe/')
    l10n_pe_cpe_summary_url_lycet_token = fields.Char('Token LYCET', required=True)
    l10n_pe_cpe_summary_journal_ids = fields.Many2many('account.journal', string='Diarios para resumen de boletas', domain="[('type', 'in', ['sale'])]",help='Diarios que se considerarán para la generación del resumen de boletas mediante cron.')