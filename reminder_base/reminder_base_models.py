from openerp import api, models, fields, SUPERUSER_ID


class reminder(models.AbstractModel):
    _name = 'reminder'

    _reminder_date_field = 'date'
    _reminder_description_field = 'description'

    reminder_event_id = fields.Many2one('calendar.event',
                                        string='Reminder Calendar Event')
    reminder_alarm_ids = fields.Many2many('calendar.alarm', string='Reminders',
                                          related='reminder_event_id.alarm_ids')

    @api.one
    def _get_reminder_event_name(self):
        return '%s: %s' % (self._description, self.display_name)

    @api.model
    def _create_reminder_event(self):
        vals = {
            'reminder_res_model': self._name,
            # dummy values
            'name': 'TMP NAME',
            'allday': True,
            'start_date': fields.Date.today(),
            'stop_date': fields.Date.today(),
        }
        event = self.env['calendar.event'].with_context({}).create(vals)
        return event

    @api.one
    def _check_update_reminder(self, vals):
        if not vals:
            return False
        fields = ['reminder_alarm_ids',
                  self._reminder_date_field,
                  self._reminder_description_field]
        if not any([k in vals for k in fields if k]):
            return False
        return True

    @api.model
    def _init_reminder(self):
        domain = [(self._reminder_date_field, '!=', False)]
        self.search(domain)._do_update_reminder()

    @api.one
    def _update_reminder(self, vals):
        if not self._check_update_reminder(vals):
            return
        self._do_update_reminder()

    @api.one
    def _do_update_reminder(self):
        vals = {'name': self._get_reminder_event_name()[0]}

        event = self.reminder_event_id
        if not event:
            event = self._create_reminder_event()
            self.reminder_event_id = event.id

        if not event.reminder_res_id:
            vals['reminder_res_id'] = self.id

        fdate = self._fields[self._reminder_date_field]
        fdate_value = getattr(self, self._reminder_date_field)
        if not fdate_value:
            event.unlink()
            return
        if fdate.type == 'date':
            vals.update({
                'allday': True,
                'start_date': fdate_value,
                'stop_date': fdate_value,
            })
        elif fdate.type == 'datetime':
            vals.update({
                'allday': False,
                'start_datetime': fdate_value,
                'stop_datetime': fdate_value,
            })
        if self._reminder_description_field:
            vals['description'] = getattr(self, self._reminder_description_field)
        event.write(vals)

    @api.model
    def _check_reminder_event(self, vals):
        fields = ['reminder_alarm_ids',
                  self._reminder_date_field]

        if any([k in vals for k in fields]):
            event = self._create_reminder_event()
            vals['reminder_event_id'] = event.id
        return vals

    @api.model
    def create(self, vals):
        vals = self._check_reminder_event(vals)
        res = super(reminder, self).create(vals)
        res._update_reminder(vals)
        return res

    @api.one
    def write(self, vals):
        if not self.reminder_event_id:
            vals = self._check_reminder_event(vals)
        res = super(reminder, self).write(vals)
        self._update_reminder(vals)
        return res


class calendar_event(models.Model):
    _inherit = 'calendar.event'

    reminder_res_model = fields.Char('Related Document Model for reminding')
    reminder_res_id = fields.Integer('Related Document ID for reminding')

    @api.multi
    def open_reminder_object(self):
        r = self[0]
        target = self._context.get('target', 'current')
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': r.reminder_res_model,
            'res_id': r.reminder_res_id,
            'views': [(False, 'form')],
            'target': target,
        }


class reminder_admin_wizard(models.TransientModel):
    _name = 'reminder.admin'

    model = fields.Selection(string='Model', selection='_get_model_list', required=True)
    events_count = fields.Integer(string='Count of calendar records', compute='_get_events_count')
    action = fields.Selection(string='Action', selection=[('create', 'Create Calendar Records'), ('delete', 'Delete Calendar Records')],
                              required=True, default='create',)

    def _get_model_list(self):
        res = []
        for r in self.env['ir.model.fields'].search([('name', '=', 'reminder_event_id')]):
            if r.model_id.model == 'reminder':
                # ignore abstract class
                continue
            res.append( (r.model_id.model, r.model_id.name) )
        return res

    @api.onchange('model')
    @api.one
    def _get_events_count(self):
        count = 0
        if self.model:
            count = self.env['calendar.event'].search_count([('reminder_res_model', '=', self.model)])
        self.events_count = count

    @api.one
    def action_execute(self):
        if self.action == 'delete':
            self.env['calendar.event'].search([('reminder_res_model', '=', self.model)]).unlink()
        elif self.action == 'create':
            self.env[self.model]._init_reminder()
