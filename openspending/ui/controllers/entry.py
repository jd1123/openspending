import logging

from pylons import request, response, tmpl_context as c
from pylons.controllers.util import abort, redirect
from pylons.i18n import _

from openspending.lib import util
from openspending.lib.browser import Browser
from openspending.plugins.core import PluginImplementations
from openspending.plugins.interfaces import IEntryController
from openspending.ui.lib.base import BaseController, render
from openspending.ui.lib.views import handle_request
from openspending.lib.csvexport import write_csv
from openspending.lib.jsonexport import write_json, to_jsonp
from openspending.ui.lib import helpers as h

log = logging.getLogger(__name__)

class EntryController(BaseController):

    extensions = PluginImplementations(IEntryController)

    def index(self, dataset):
        self._get_dataset(dataset)
        handle_request(request, c, c.dataset)
        url = h.url_for(controller='entry', action='index', dataset=c.dataset.name)

        c.facet_dimensions = c.dataset.facet_dimensions
        c.facets = _fetch_facets(c.facet_dimensions)

        return render('entry/index.html')

    def index_export(self, dataset, format):
        self._get_dataset(dataset)

        if format == 'json':
            return write_json(c.dataset.entries(), response, filename=c.dataset.name + '.json')
        if format == 'csv':
            return write_csv(c.dataset.entries(), response, filename=c.dataset.name + '.csv')
        else:
            return redirect(h.url_for(controller='entry', action='index'))

    def view(self, dataset, id, format='html'):
        self._get_dataset(dataset)
        entries = list(c.dataset.entries(c.dataset.alias.c.id==id))
        if not len(entries) == 1:
            abort(404, _('Sorry, there is no entry %r') % id)
        c.entry = entries.pop()

        c.id = c.entry.get('id')
        c.from_ = c.entry.get('from')
        c.to = c.entry.get('to')
        c.currency = c.entry.get('currency', c.dataset.currency).upper()
        c.amount = c.entry.get('amount')
        c.time = c.entry.get('time')

        c.custom_html = h.render_entry_custom_html(c.dataset,
                                                   c.entry)

        excluded_keys = ('time', 'amount', 'currency', 'from',
                         'to', 'dataset', 'id', 'name', 'description')

        c.extras = {}
        if c.dataset:
            c.desc = dict([(d.name, d) for d in c.dataset.dimensions])
            for key in c.entry:
                if key in c.desc and \
                        not key in excluded_keys:
                    c.extras[key] = c.entry[key]

        for item in self.extensions:
            item.read(c, request, response, c.entry)

        if format == 'json':
            return to_jsonp(c.entry)
        elif format == 'csv':
            return write_csv([c.entry], response)
        else:
            return render('entry/view.html')

def _fetch_facets(dimensions):
    fields = [d.name for d in dimensions]
    _, facets, _ = Browser(pagesize=0, facet_field=fields).execute()

    for dim in dimensions:
        if dim.is_compound:
            member_names = [x[0] for x in facets[dim.name]]
            facet_values = [x[1] for x in facets[dim.name]]
            members = dim.members(dim.alias.c.name.in_(member_names))
            members = util.sort_by_reference(member_names, members, lambda x: x['name'])
            facets[dim.name] = zip(members, facet_values)

    return facets
