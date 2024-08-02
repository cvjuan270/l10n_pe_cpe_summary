# -*- coding: utf-8 -*-
import datetime
import calendar
import logging
import requests
import json
import pytz
import base64

from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from json.decoder import JSONDecodeError


_logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    "request": "Hubo un error al comunicarse con el servicio de LYCET" + " " + "Detalles:",
    "json_decode": "No se pudo decodificar la respuesta recibida de SUNAT." + " " + "Detalles:",
    "unzip": "No se pudo descomprimir el archivo ZIP recibido de SUNAT.",
    "response_code": "SUNAT devolvió un código de error." + " " + "Detalles:",
    "response_unknown": "No se pudo identificar el contenido en la respuesta recuperada de SUNAT." + " " + "Detalles:",
    'unauthorized': 'El token de acceso es inválido o ha expirado. Por favor, actualice el token de acceso en la configuración de la compañía.',
}
peru_tz = pytz.timezone('America/Lima')


class L10n_pe_cpe_summary(models.Model):
    _name = 'l10n_pe_cpe.summary'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = _('Resumen de diario de Boletas')

    name = fields.Char('Correlativo', required=True, readonly=True, copy=False, default='/')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('generate', 'Generado'),
        ('sent', 'Enviado'),
        ('verify', 'Esperando'),
        ('done', 'Hecho'),
        ('cancel', 'Cancelado'),
    ], string='Estado', index=True, readonly=True, default='draft', tracking=True, copy=False)

    estate_sunat = fields.Selection([
        ('01', 'Registrado'),
        ('03', 'Enviado'),
        ('05', 'Aceptado'),
        ('07', 'Observado'),
        ('09', 'Rechazado'),
        ('11', 'Anulado'),
        ('13', 'Por anular'),
    ], string='Estado Sunat', default=None, readonly=True, copy=False, tracking=True)

    ticket = fields.Char("Ticket", readonly=True)
    cdr_filename = fields.Char("Nombre de archivo CDR", readonly=True)
    cdr_file = fields.Binary("Archivo CDR", readonly=True)

    start_date = fields.Date("Fecha Inicio", default=fields.Date.context_today, )
    end_date = fields.Date("Fecha Final", default=fields.Date.context_today)
    send_date = fields.Datetime("Fecha de envio", readonly=True)
    company_id = fields.Many2one('res.company', 'Compañía', required=True, default=lambda self: self.env.company,
                                 readonly=True)
    journal_ids = fields.Many2many('account.journal', string='Diarios', required=True,
                                   domain=[
                                       ('type', '=', 'sale'),
                                       ('l10n_latam_use_documents', '=', True)
                                   ])
    summary_line_ids = fields.One2many('l10n_pe_cpe.summary.line', 'summary_id', 'Líneas de resumen', copy=False, readonly=True)

    def _check_required_data(self, lines):
        errors = []
        for line in lines:
            if not line.cliente_tipo or line.cliente_tipo not in ['1', '0']:
                errors.append(_('El tipo de documento del Cliente CPE %s no está configurado.') % line.serie_numero)
            if not line.cliente_numero or len(line.cliente_numero) != 8:
                errors.append('El número de documento del Cliente CPE %s no está configurado correctamente' % line.serie_numero)
            if not line.mnto_oper_gravadas:
                errors.append('El monto de operaciones gravadas del CPE %s no está establcido' % line.serie_numero)
            if not line.mnto_igv:
                errors.append('El monto de IGV del CPE %s no está establcido' % line.serie_numero)
        return errors


    def _get_domain(self):
        self.ensure_one()

        document_type_id = self.env['l10n_latam.document.type'].search([('code', '=', '03')], limit=1)
        domain = [
            ('move_type', 'in', ['out_invoice']),
            ('state', '=', 'posted'),
            ('edi_state', 'in', ['to_send',None]),
            ('company_id', '=', self.company_id.id),
            ('journal_id', 'in', self.journal_ids.ids),
            ('l10n_latam_document_type_id', '=', document_type_id.id),
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date),
        ]
        return domain

    def action_confirm(self):
        self.ensure_one()
        if self.name == '/':
            summary_sequence = self.env['ir.sequence'].search([('code', '=', 'l10n_pe_cpe.summary'),
                                                            ('company_id', '=', self.company_id.id)], limit=1)
            if not summary_sequence:
                now = datetime.datetime.now()
                _, last_day = calendar.monthrange(now.year, now.month)
                last_day_month = datetime.date(now.year, now.month, last_day)
                summary_sequence = self.env['ir.sequence'].sudo().create({
                    'name': 'Resumen Diario de Boletas',
                    'code': 'l10n_pe_cpe.summary',
                    'padding': 4,
                    'company_id': self.company_id.id,
                    'use_date_range': True,
                    'implementation': 'standard',
                    'date_range_ids': [(0, 0, {'date_from': self.start_date, 'date_to': last_day_month})],
                    'prefix': 'RC-%(year)s%(month)s-',
                    'number_next': 1,
                    'number_increment': 1,
                })
            self.name = summary_sequence.next_by_id()
        self.write({'state': 'generate'})
        self._create_summary_lines()
        return True

    def _create_summary_lines(self):
        self.ensure_one()
        self.summary_line_ids.unlink()
        domain = self._get_domain()
        invoices = self.env['account.move'].search(domain)
        for invoice in invoices:
            self.env['l10n_pe_cpe.summary.line'].create({
                'summary_id': self.id,
                'move_id': invoice.id,
            })
        return True

    def _create_values(self):
        self.ensure_one()

        def _get_details():
            self.ensure_one()
            details = []
            for line in self.summary_line_ids:
                values = {
                    'tipoDoc': line.move_id.l10n_latam_document_type_id.code,
                    'serieNro': line.serie_numero,
                    'clienteTipo': line.cliente_tipo,
                    'clienteNro': line.cliente_numero,
                    'estado': '1',
                    'total': line.total,
                    'mtoOperGravadas': line.mnto_oper_gravadas,
                    'mtoIGV': line.mnto_igv,
                }
                details.append(values)
            return details

        values = {
            'correlativo': self.name.split('-')[2],
            'fecGeneracion': datetime.datetime.now(peru_tz).strftime('%Y-%m-%dT%H:%M:%S-05:00'),
            'fecResumen': datetime.datetime.now(peru_tz).strftime('%Y-%m-%dT%H:%M:%S-05:00'),
            'moneda': 'PEN',
            'company': {
                'ruc': self.company_id.vat.strip(),
                'razonSocial': self.company_id.name.strip(),
                'nombreComercial': self.company_id.name.strip(),
                'address': {
                    'ubigueo': self.company_id.partner_id.zip,
                    'codigoPais': 'PE',
                    'departamento': self.company_id.partner_id.state_id.name or '',
                    'provincia': self.company_id.partner_id.city or '',
                    'distrito': self.company_id.partner_id.l10n_pe_district.name or '',
                    'urbanizacion': '-',
                    'direccion': self.company_id.partner_id.street or '-'
                }
            },
            'details': _get_details()
        }
        print(json.dumps(values, indent=2, ensure_ascii=False))
        return json.dumps(values)

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.ensure_one()
        self.summary_line_ids.unlink()
        self.write({
            'state': 'draft',
            'estate_sunat': False,
            'ticket': False,})
        return True

    def action_send(self):
        self.ensure_one()
        errors = self._check_required_data(self.summary_line_ids)
        if errors:
            raise UserError('\n'.join(errors))

        json_values = self._create_values()

        # guardar el json en un archivo
        attachment = self.env['ir.attachment'].create({
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'name': '%s.json' % self.name,
            'datas': base64.b64encode(json_values.encode('utf-8')),
            'mimetype': 'application/json',
        })

        #agregar mensaje al resumen
        self.message_post(body=_('Resumen de diario de boletas generado'), attachment_ids=[attachment.id])

        url = self.company_id.l10n_pe_cpe_summary_url_lycet+'/api/v1/summary/send'
        response = self._post_request_lycet_api(url, json_values)
        if response.get('error'):
            raise UserError(response.get('error'))
        if response.get('sunatResponse') and response.get('sunatResponse').get('error'):
            error_code = response.get('sunatResponse').get('error').get('code')
            error_message = response.get('sunatResponse').get('error').get('message')
            raise UserError('Error %s: %s' % (error_code, error_message))

        self.write({'state': 'sent',
                    'send_date': fields.Datetime.now(),
                    'ticket': response.get('sunatResponse').get('ticket')})
        
        return True

    def action_void(self):
        self.write({'state': 'verify'})
        return True

    def action_verify(self):
        self.ensure_one()
        if not self.ticket:
            raise ValidationError(_('No se ha enviado el resumen.'))
        url = self.company_id.l10n_pe_cpe_summary_url_lycet+'/api/v1/summary/status'
        response = self._get_request_ticket_lycet_api(url, self.ticket)
        if response.get('error'):
            raise UserError(str(response.get('error')))
        if response.get('sunatResponse') and response.get('sunatResponse').get('error'):
            error_code = response.get('sunatResponse').get('error').get('code')
            error_message = response.get('sunatResponse').get('error').get('message')
            raise UserError('Error %s: %s' % (error_code, error_message))
        
        if response.get('code') == '99':
            self.message_post(body='Error %s: %s' % (response.get('cdrResponse'), response.get('description')))
            raise UserError('Error %s: %s' % (response.get('cdrResponse'), response.get('description')))

        if response.get('code') != '0':
            raise UserError('Error  Desconocido%s: %s' % (str(response)))

        attachment = self.env['ir.attachment'].create({
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary',
                'name': '%s.zip' % self.name,
                'datas': response.get('cdrZip'),
                'mimetype': 'application/zip',
            })


        # update account.edi.document
        
        for line in self.summary_line_ids:
            account_edi_document = self.env['account.edi.document'].search([('move_id', '=', line.move_id.id)], limit=1)
            if not account_edi_document:
                edi_format = self.env['account.edi.format'].search([('code', '=', 'pe_ubl_2_1')], limit=1)
                if not edi_format:
                    edi_format = self.env['account.edi.format'].search([('code', '=', 'ubl_2_1')], limit=1)
                account_edi_document = self.env['account.edi.document'].create({
                    'move_id': line.move_id.id,
                    'state': 'sent',
                    'edi_format_id': edi_format.id,
                    'attachment_id': attachment.id,
                    'blocking_level': False,
                    'error': False,
                })
            account_edi_document.write({
                'state': 'sent',
                'blocking_level': False,
                    'error': False,
            })

            line.move_id.write({
                'edi_state': 'sent',
            })
            
            message = _("CPE aceptado por SUNAT.<br/> Enviado mediante el resumen diario de boletas %s") % (self.name)
            line.move_id.with_context(no_new_invoice=True).message_post(
                body=message,
                attachment_ids=[attachment.id],
            )
            
        self.write({
            'state': 'done',
            'estate_sunat': '05',
            'cdr_filename': str(response.get('cdrResponse').get('id'))+'.zip',
            'cdr_file': response.get('cdrZip'),
        })
        return True

    def _post_request_lycet_api(self, url, json_values):
        url = url + '?token=' + self.company_id.l10n_pe_cpe_summary_url_lycet_token
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(url, data=json_values, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            to_return = {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["request"], e))}
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                to_return["error_reason"] = "unauthorized"
            return to_return
        try:
            response_json = response.json()
            return response_json
        except JSONDecodeError as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["json_decode"], e))}

    def _get_request_ticket_lycet_api(self, url, ticket):
        url = url + '?token=%s&ruc=%s&ticket=%s' % (self.company_id.l10n_pe_cpe_summary_url_lycet_token,self.company_id.vat, ticket)
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            to_return = {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["request"], e))}
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                to_return["error_reason"] = "unauthorized"
            return to_return
        try:
            response_json = response.json()
            return response_json
        except JSONDecodeError as e:
            return {"error": str(Markup("%s<br/>%s") % (ERROR_MESSAGES["json_decode"], e))}

    # -------------------------------------------------------------------------
    # CRON
    # -------------------------------------------------------------------------
    
    ## cron para crear resumen de boletas
    def _cron_create_summary(self):
        companies = self.env['res.company'].search([('country_id.code', '=', 'PE')])
        for company in companies:
            journals = company.l10n_pe_cpe_summary_journal_ids
            if not journals:
                journals = self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('l10n_latam_use_documents', '=', True),
                    ('company_id', '=', company.id)
                ])
            if not journals:
                continue
            summarie = self.env['l10n_pe_cpe.summary'].create([
                {
                'start_date': datetime.datetime.now(peru_tz).strftime('%Y-%m-%d'),
                'end_date': datetime.datetime.now(peru_tz).strftime('%Y-%m-%d'),
                # 'send_date': datetime.datetime.now(peru_tz).strftime('%Y-%m-%d %H:%M:%S'),
                'company_id': company.id,
                'journal_ids': [(6, 0, journals.ids)],
                }
            ])
            result = summarie.action_confirm()
            if result and summarie.summary_line_ids:
                summarie.action_send()

    ## cron para verificar resumen de boletas
    def _cron_verify_summary(self):
        summaries = self.env['l10n_pe_cpe.summary'].search([('state', '=', 'sent'), ('ticket', '!=', False),( 'estate_sunat', 'not in', ['05', '07', '09','11'])])
        for summary in summaries:
            summary.action_verify()

