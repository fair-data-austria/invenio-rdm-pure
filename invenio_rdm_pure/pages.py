# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Technische Universität Graz
#
# invenio-rdm-pure is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""File description."""

import json

from .source.pure.requests_pure import get_pure_metadata
from .source.rdm.add_record import RdmAddRecord
from .source.reports import Reports
from .source.utils import initialize_counters


class RunPages:
    """Runpages."""

    def __init__(self):
        """init."""
        self.report = Reports()
        self.rdm_add_record = RdmAddRecord()

    def get_pure_by_page(self, page_begin: int, page_end: int, page_size: int):
        """Gets records from Pure 'research-outputs' endpoint by page and submit them to RDM."""
        for page in range(page_begin, page_end):
            self.global_counters = initialize_counters()
            # Report intro
            self.report.add_template(["console"], ["general", "title"], ["PAGES"])
            self.report.add_template(
                ["console"], ["pages", "page_and_size"], [page, page_size]
            )
            # Pure get request
            response = get_pure_metadata(
                "research-outputs", "", {"page": page, "pageSize": page_size}
            )
            # Load json response
            resp_json = json.loads(response.content)
            # Creates data to push to RDM
            for item in resp_json["items"]:
                self.report.add("")  # adds new line in the console
                self.rdm_add_record.create_invenio_data(self.global_counters, item)
            self.report_summary(page, page_size)

    def report_summary(self, pag, page_size):
        """report_summary."""
        # Global counters
        self.report.summary_global_counters(["console"], self.global_counters)
        # Summary pages.log
        self.report.pages_single_line(self.global_counters, pag, page_size)
