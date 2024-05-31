# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class L10n_pe_cpeSummaryLine(models.Model):
    _name = 'l10n_pe_cpe.summary.line'
    _description = _('L10n_pe_cpeSummaryLine')

    summary_id = fields.Many2one('l10n_pe_cpe.summary', 'Resumen', required=True, ondelete='cascade')
    move_id = fields.Many2one('account.move', 'Boleta', required=True)

    serie_numero = fields.Char('Serie y Número', compute='_compute_serie_numero')
    cliente_tipo = fields.Char('Tipo de Cliente', compute='_compute_cliente_tipo')
    cliente_numero = fields.Char('Número de Cliente', related='move_id.partner_id.vat')
    total = fields.Float('Total', compute='_compute_total')
    mnto_oper_gravadas = fields.Float('Monto Operaciones Gravadas', compute='_compute_mnto_oper_gravadas')
    mnto_igv = fields.Float('Monto IGV', compute='_compute_mnto_igv')
    # compute serie_numero for move_id.name
    @api.depends('move_id')
    def _compute_serie_numero(self):
        for record in self:
            numero = record.move_id.name.split('-')[1].strip()
            serie = record.move_id.name.split('-')[0].replace(' ', '')[-4:]
            record.serie_numero = '%s-%s' % (serie, numero)

    # compute cliente_tipo for move_id.partner_id.l10n_latam_identification_type_id.code
    @api.depends('move_id')
    def _compute_cliente_tipo(self):
        for record in self:
            record.cliente_tipo = record.move_id.partner_id.parent_id.l10n_latam_identification_type_id.l10n_pe_vat_code if record.move_id.partner_id.parent_id else record.move_id.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code

    # compute cliente_numero for move_id.partner_id.vat
    @api.depends('move_id')
    def _compute_cliente_numero(self):
        for record in self:
            record.cliente_numero = record.move_id.partner_id.parent_id.vat if record.move_id.partner_id.parent_id else record.move_id.partner_id.vat

    # compute total for move_id.amount_total
    @api.depends('move_id')
    def _compute_total(self):
        for record in self:
            record.total = record.move_id.amount_total_signed

    # compute mnto_oper_gravadas for move_id.amount_untaxed
    @api.depends('move_id')
    def _compute_mnto_oper_gravadas(self):
        for record in self:
            record.mnto_oper_gravadas = record.move_id.amount_untaxed_signed

    # compute mnto_igv for move_id.amount_tax
    @api.depends('move_id')
    def _compute_mnto_igv(self):
        for record in self:
            # sum amount tax is tax_group_id = IGV
            record.mnto_igv = sum([line.amount_currency*-1 for line in record.move_id.line_ids if line.tax_group_id.name == 'IGV'])
