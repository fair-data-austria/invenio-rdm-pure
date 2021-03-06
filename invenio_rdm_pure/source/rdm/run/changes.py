# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Technische Universität Graz
#
# invenio-rdm-pure is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""File description."""

import json
from datetime import datetime, timedelta

from ....setup import data_files_name
from ...pure.requests_pure import get_next_page, get_pure_metadata
from ...reports import Reports
from ...utils import add_spaces, check_if_file_exists, initialize_counters
from ..add_record import RdmAddRecord
from ..delete_record import Delete
from ..requests_rdm import Requests


class PureChanges:
    """Description."""

    def __init__(self):
        """Description."""
        self.add_record = RdmAddRecord()
        self.report = Reports()
        self.delete = Delete()
        self.rdm_requests = Requests()

    def get_pure_changes(self):
        """Gets from Pure 'changes' endpoint all records that have been created / updated / deleted.

        and modifies accordingly the relative RDM records.
        """
        # Get date of last update
        missing_updates = self._get_missing_updates()

        if missing_updates == []:
            self.report.add("\nNothing to update.\n")
            return

        for date_to_update in reversed(missing_updates):
            self._changes_by_date(date_to_update)
        return

    def _set_counters_and_title(func):
        """Description."""

        def _wrapper(self, changes_date: str):
            """Description."""
            # Initialize global counters
            self.global_counters = initialize_counters()

            self.report_files = ["console", "changes"]

            self.report.add_template(
                self.report_files, ["general", "title"], ["CHANGES"]
            )
            self.report.add(f"\nProcessed date: {changes_date}", self.report_files)

            # Decorated function
            func(self, changes_date)

            self._report_summary()

        return _wrapper

    @_set_counters_and_title
    def _changes_by_date(self, changes_date: str):
        """Gets from Pure all changes that took place in a certain date."""
        reference = changes_date
        page = 1

        while reference:
            # Get from pure all changes of a certain date
            response = get_pure_metadata("changes", reference, {})

            if response.status_code >= 300:
                self.report.add(response.content, self.report_files)
                return False

            # Check if there are records in the response from pure
            json_response = self._records_to_process(response, page, changes_date)

            # If there are no records to process
            if not json_response:
                return True

            # Used to check if there are doubled tasks (e.g. update uuid and delete same uuid)
            self.duplicated_uuid = []

            self._initialize_local_counters()

            # Iterates over all records that need to be deleted
            self._delete_records(json_response)

            # Create / Add / Update
            self._update_records(json_response)

            # Gets the reference code of the next page
            reference = get_next_page(json_response).split("/")[-1]

            page += 1

    def _records_to_process(self, response: object, page: int, changes_date: str):
        """Check if there are records in the response from pure."""
        # Load response json
        json_response = json.loads(response.content)

        number_records = json_response["count"]

        if number_records == 0:
            # Adds the date to successful_changes.txt
            open(data_files_name["successful_changes"], "a").write(f"{changes_date}\n")

            if page == 1:
                # If there are no changes at all
                self.report.add(f"\n\nNothing to transfer.\n\n", self.report_files)
            return False

        report_line = f"\nPag{add_spaces(page)} @ Pure get changes @ {response} @ Number of items: {add_spaces(number_records)}"
        self.report.add(report_line, self.report_files)

        return json_response

    def _delete_records(self, json_response: dict):
        """Iterates over the Pure response and process all records that need to be deleted."""
        for item in json_response["items"]:

            if "changeType" not in item or "uuid" not in item:
                continue
            elif item["familySystemName"] != "ResearchOutput":
                continue
            elif item["changeType"] != "DELETE":
                continue

            uuid = item["uuid"]
            self.duplicated_uuid.append(uuid)
            self.local_counters["delete"] += 1

            report = f"\n{self.local_counters['delete']} @ {item['changeType']}"
            self.report.add(report)

            # Gets the record recid
            recid = self.rdm_requests.get_recid(uuid, self.global_counters)

            if recid:
                # Deletes the record from RDM
                self.delete.record(recid)
            else:
                # The record is not in RDM
                self.global_counters["delete"]["success"] += 1
        return True

    def _update_records(self, json_response: dict):
        """Iterates over the Pure response and process all records that need to be created/updated."""
        for item in json_response["items"]:

            if "changeType" not in item or "uuid" not in item:
                self.local_counters["incomplete"] += 1
                continue
            elif item["familySystemName"] != "ResearchOutput":
                self.local_counters["not_ResearchOutput"] += 1
                continue
            elif item["changeType"] == "DELETE":
                continue

            uuid = item["uuid"]
            if uuid in self.duplicated_uuid:
                self.local_counters["duplicated"] += 1
                continue

            record_number = add_spaces(self.global_counters["total"] + 1)
            report = f"\n{record_number} - Change type           - {item['changeType']}"
            self.report.add(report)

            if item["changeType"] == "ADD" or item["changeType"] == "CREATE":
                self.local_counters["create"] += 1

            if item["changeType"] == "UPDATE":
                self.local_counters["update"] += 1

            # Checks if this uuid has already been created / updated / deleted
            self.duplicated_uuid.append(uuid)

            # Adds record to RDM
            self.add_record.push_record_by_uuid(self.global_counters, uuid)

    def _get_missing_updates(self):
        """Reading successful_changes.txt gets the dates in which Pure changes have not been processed."""
        file_name = data_files_name["successful_changes"]
        check_if_file_exists(file_name)

        missing_updates = []
        count = 0
        days_span = 7

        date_today = str(datetime.today().strftime("%Y-%m-%d"))
        date_check = datetime.strptime(date_today, "%Y-%m-%d").date()

        while count < days_span:

            if str(date_check) not in open(file_name, "r").read():
                missing_updates.append(str(date_check))

            date_check = date_check - timedelta(days=1)
            count += 1

        return missing_updates

    def _report_summary(self):
        """Description."""
        # Global counters
        self.report.summary_global_counters(self.report_files, self.global_counters)

        arguments = []
        for i in self.local_counters:
            arguments.append(add_spaces(self.local_counters[i]))
        self.report.add_template(self.report_files, ["changes", "summary"], arguments)
        return

    def _initialize_local_counters(self):
        """Description."""
        # Incomplete:  when the uuid or changeType are not specified
        # Duplicated:  e.g. when a record has been modified twice in a day
        # Irrelevant:  when familySystemName is not ResearchOutput

        self.local_counters = {
            "delete": 0,
            "update": 0,
            "create": 0,
            "incomplete": 0,
            "duplicated": 0,
            "not_ResearchOutput": 0,
        }
