#!/usr/bin/env python3

'''
jira_handler.py

This module provides a Jira class for interacting with the Jira API.

It requires the "requests" library and provides functionalities to interact with
Jira by creating issues, epics, linking issues, and validating credentials.
'''

import json
import logging
import requests
from typing import Optional, Dict, List, Any

MAX_RESPONSE_LOG_SIZE = 2500  # Set a threshold for response DEBUG log size


class Jira:
    def __init__(self, jira_url: str, jira_api_base_url: str, jira_token: str, jira_special_fields: Dict[str, Any]):
        '''
        Initializes a new instance of the Jira class.

        Args:
            jira_url (str): The base URL of the Jira instance.
            jira_api_base_url (str): The base URL for Jira API requests.
            jira_token (str): The API token for authenticating Jira requests.
            jira_special_fields (Dict[str, Any]): Configuration dictionary containing fields related to Jira API interactions.

        Raises:
            RuntimeError: If the Jira URL or token validation fails.
        '''
        self.jira_url = jira_url
        self.jira_api_base_url = (
            f'{self.jira_url}{jira_api_base_url}' if jira_api_base_url.startswith('/')
            else f'{self.jira_url}/{jira_api_base_url}'
        )
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {jira_token}',
            'Content-Type': 'application/json'
        }
        self.name_format_fields = jira_special_fields.get(
            'name_format_fields', [])
        self.key_format_fields = jira_special_fields.get(
            'key_format_fields', [])
        self.custom_field_mapping = jira_special_fields.get(
            'custom_field_mapping', {})
        self.post_creation_update_fields = jira_special_fields.get(
            'post_creation_update_fields', [])
        self.array_format_fields = jira_special_fields.get(
            'array_format_fields', [])

        self._validate_credentials()

    def _validate_credentials(self) -> None:
        '''
        Validate the Jira URL and token by making a simple request to the Jira API.

        Raises:
            RuntimeError: If the Jira URL or token validation fails.

        Notes:
            This method is called during initialization (`__init__`) to ensure the Jira API
            credentials are valid before proceeding with other operations.
        '''
        logging.debug('Validating Jira URL and token')
        validate_url = f'{self.jira_api_base_url}/myself'

        response = requests.get(validate_url, headers=self.headers)
        if response.status_code != 200:
            logging.error(
                f'Failed to validate Jira URL or token. The Jira API request responded with a "{response.status_code}" status code.')
            logging.info('Make sure the Jira URL and token are set correctly.')
            logging.info('You can get a Jira API token from - '
                         f'{self.jira_url}/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens.')
            raise RuntimeError(
                'Failed to validate Jira URL or token. Check log for details.')

    def send_request(self,
                     api_type: Optional[str] = None,
                     custom_jira_api_base_url: Optional[str] = None,
                     issue_key: Optional[str] = None,
                     jira_request_data: Optional[Dict[str, Any]] = None,
                     method: Optional[str] = 'post') -> Dict[str, Any]:
        '''
        Send a request to the Jira API and return the parsed response.

        Args:
            api_type (str): Type of the API endpoint (e.g., 'issue', 'board').
            custom_jira_api_base_url (Optional[str]): Custom base URL for the Jira API request.
            issue_key (Optional[str]): The key of the issue for PUT requests.
            jira_request_data (Optional[Dict[str, Any]]): Data to send in the request.
            method (Optional[str]): HTTP method to use ('post', 'put', 'get'). Defaults to 'post'.

        Returns:
            Dict[str, Any]: Parsed response from the Jira API.

        Raises:
            requests.exceptions.RequestException: If the request to Jira fails.
            ValueError: If an invalid HTTP method is used.
        '''
        if method.lower() not in ['post', 'put', 'get']:
            raise ValueError(
                'Invalid HTTP method. Allowed methods are "post", "put", "get".')

        if custom_jira_api_base_url:
            url = custom_jira_api_base_url
        else:
            if method.lower() in ['put', 'get'] and issue_key:
                url = f'{self.jira_api_base_url}/{api_type}/{issue_key}'
            else:
                url = f'{self.jira_api_base_url}/{api_type}'

        logging.debug(f'Sending a Jira {method.upper()} request to '
                      f'"{url}" with the following DATA: {jira_request_data}')
        try:
            if method.lower() == 'post':
                response = requests.post(
                    url, headers=self.headers, json=jira_request_data)
            elif method.lower() == 'put':
                response = requests.put(
                    url, headers=self.headers, json=jira_request_data)
            elif method.lower() == 'get':
                response = requests.get(
                    url, headers=self.headers, params=jira_request_data)

            response.raise_for_status()  # Raise exception for non-2xx response codes
            # Check if response is not empty and is valid JSON
            if response.text:
                try:
                    # Conditionally log the response JSON based on its size
                    response_json = response.json()
                    if len(json.dumps(response_json)) <= MAX_RESPONSE_LOG_SIZE:
                        logging.debug(f'Request response: {response_json}')
                    else:
                        logging.debug(f'Request response is too large to log '
                                      f'(size: {len(json.dumps(response_json))} bytes)')
                except ValueError:
                    logging.error(
                        f'Return Non-JSON response as text: {response.text}')
                    return {'response_text': response.text}
            else:
                response_json = response

            return response_json
        except requests.exceptions.RequestException as e:
            logging.error(f'Error in Jira API request: {str(e)}')
            try:
                # Try to get the response as JSON
                response_json = response.json()
                logging.error(f'Request response JSON: {response_json}')
            except ValueError:
                # Handle cases where response is not valid JSON
                logging.error(
                    f'Request response: {response.text if response else "No response"}')

            raise e  # Re-raise the exception for handling at a higher level

    def get_project_id_by_key(self, project_key: str) -> str:
        '''
        Get the ID of a Jira project by its key.

        Args:
            project_key (str): The key of the project.

        Returns:
            str: The ID of the project.

        Raises:
            RuntimeError: If the project key is not found.
        '''
        response = self.send_request(api_type='project', method='get')

        for project in response:
            if project['key'] == project_key:
                return project['id']

        raise RuntimeError(f'Project key "{project_key}" not found.')

    def get_board_ids_by_project_key(self, project_key: str) -> List[str]:
        '''
        Return **all** Scrum board IDs (type='scrum') for the given project, skipping Kanban boards.
        '''
        project_id = self.get_project_id_by_key(project_key)
        search_project_boards_url = f'{self.jira_url}/rest/agile/1.0/board?projectKeyOrId={project_id}'
        response = self.send_request(
            custom_jira_api_base_url=search_project_boards_url, method='get')

        board_ids: List[str] = []
        for board in response.get('values', []):
            if board.get('type') == 'scrum':
                board_ids.append(str(board['id']))

        if not board_ids:
            raise RuntimeError(f'No boards (Scrum) found for project key "{project_key}".')
        return board_ids

    def get_sprint_id_from_all_boards(self, project_key: str, sprint_name: str) -> Optional[str]:
        '''
        Search for a sprint across all Scrum boards in the project.
        Returns the first matching sprint ID, or None if not found in any board.
        '''
        board_ids = self.get_board_ids_by_project_key(project_key)
        for b_id in board_ids:
            possible_sprint_id = self.get_sprint_id(b_id, sprint_name)
            if possible_sprint_id:
                logging.debug(f'Sprint "{sprint_name}" was found in board {b_id}.')
                return possible_sprint_id

        logging.error(f'Sprint "{sprint_name}" was not found in the "{project_key}" project.')
        return None

    def get_sprint_id(self, board_id: str, sprint_name: str) -> Optional[str]:
        '''
        Get the ID of a sprint by its name on a given scrum board.
        - Fetches active and future sprints (to be safe).
        - Handles pagination if there are more than 50 sprints.
        - Logs all sprint names to help debug mismatch issues.
        '''
        logging.debug(
            f'Looking for sprint "{sprint_name}" on board {board_id}, including active/future.'
        )
        base_url = f'{self.jira_url}/rest/agile/1.0/board/{board_id}/sprint'
        states = "active,future"
        start_at = 0
        max_results = 50  # default page size

        while True:
            logging.debug(f'Fetching sprints with startAt={start_at} (page size={max_results})...')
            response = self.send_request(
                custom_jira_api_base_url=base_url,
                method='get',
                jira_request_data={
                    "state": states,
                    "startAt": start_at,
                    "maxResults": max_results
                }
            )
            sprint_values = response.get('values', [])
            if sprint_values:
                # logging.debug(f'Found {len(sprint_values)} sprints on this page.')
                for sprint in sprint_values:
                    jira_sprint_name = sprint.get('name')
                    if jira_sprint_name.strip().lower() == sprint_name.strip().lower():
                        return sprint.get('id')
            else:
                logging.debug('No sprints found on this page.')

            # Check pagination
            is_last = response.get('isLast', True)
            start_at += max_results

            if is_last:
                break

        logging.debug(f'Sprint "{sprint_name}" not found in board {board_id}.')
        return None

    def link_jira_issues(self,
                         issue_key: str,
                         issue_parent_key: str,
                         link_type: str = 'Related') -> Dict[str, Any]:
        '''
        Link two Jira issues with a specified relationship type.

        Args:
            issue_key (str): The key of the Jira issue to link (outward issue).
            issue_parent_key (str): The key of the Jira issue to link to (inward issue).
            link_type (str, optional): The type of relationship between the issues. Defaults to 'Related'.

        Returns:
            Dict[str, Any]: The response from the Jira API after linking the issues.
        '''
        link_data = {
            'type': {'name': link_type},
            'inwardIssue': {'key': issue_key},
            'outwardIssue': {'key': issue_parent_key}
        }
        return self.send_request(api_type='issueLink', method='post', jira_request_data=link_data)

    def _build_issue_data(self,
                          jira_project: str,
                          fields: Dict[str, Any],
                          exclude_fields: List[str] = []) -> Dict[str, Any]:
        '''
        Build the data structure for a Jira issue.

        Args:
            jira_project (str): The key of the project where the issue will be created.
            fields (Dict[str, Any]): A dictionary containing the fields and their values for the issue.
            exclude_fields (List[str], optional): A list of field names to exclude from the issue data. Defaults to an empty list.

        Returns:
            Dict[str, Any]: The data structure for the issue.
        '''

        # Helper function to transform field values for string or dict
        def transform_field_value(field_value, key_type):
            if isinstance(field_value, dict):
                # Fix: use .items() to properly iterate through dictionary key-value pairs
                return [{key_type: val} for key, val in field_value.items()]
            else:
                return {key_type: field_value}

        # Initializes a new dict for the issue data
        issue_data = {'fields': {}}

        # Get the list of fields that should be formatted as arrays
        array_fields = getattr(self, 'array_format_fields', [])

        for field_name, field_value in fields.items():
            if field_name == 'issues':
                # The 'issues' key contains a list of child issues that will be created later
                continue
            if field_name in exclude_fields:
                continue
            if field_name == 'issuelinks':
                # The 'issuelinks' will be handled later by the link_jira_issues def
                continue

            if field_name in self.key_format_fields:
                # Fields that require 'key' format
                value = transform_field_value(field_value, 'key')
                # Ensure array formatting if needed
                if field_name in array_fields and not isinstance(value, list):
                    value = [value]
                issue_data['fields'][field_name] = value
            elif field_name in self.name_format_fields:
                # Fields that require 'name' format
                value = transform_field_value(field_value, 'name')
                # Ensure array formatting if needed
                if field_name in array_fields and not isinstance(value, list):
                    value = [value]
                issue_data['fields'][field_name] = value
            elif field_name in self.custom_field_mapping:
                if field_name == "sprint":
                    custom_field_name = self.custom_field_mapping[field_name]
                    sprint_id = self.get_sprint_id_from_all_boards(jira_project, field_value)
                    issue_data['fields'][custom_field_name] = sprint_id
                elif field_name == "AssignedTeam":
                    # Handle AssignedTeam as a value-format field (select dropdown)
                    custom_field_name = self.custom_field_mapping[field_name]
                    issue_data['fields'][custom_field_name] = {"value": field_value}
                else:
                    issue_data['fields'][self.custom_field_mapping[field_name]] = field_value
            elif field_name in self.custom_field_mapping.get('key_format_fields', {}):
                # Custom fields that require 'key' format
                custom_field_name = self.custom_field_mapping['key_format_fields'][field_name]
                issue_data['fields'][custom_field_name] = transform_field_value(
                    field_value, 'key')
            elif field_name in self.custom_field_mapping.get('name_format_fields', {}):
                # Custom fields that require 'name' format
                custom_field_name = self.custom_field_mapping['name_format_fields'][field_name]
                issue_data['fields'][custom_field_name] = transform_field_value(
                    field_value, 'name')
            else:
                # Non-special fields
                issue_data['fields'][field_name] = field_value
        return issue_data

    def create_new_jira_issue(self,
                              jira_project: str,
                              jira_issue: Dict[str, Any],
                              epic_key: Optional[str] = None,
                              parent_key: Optional[str] = None) -> Dict[str, Any]:
        '''
        Create a new Jira issue in a specified project and optionally link it to an epic or parent issue.
        Handle sub-tasks by linking them to a parent issue.
        Some fields are updated post-creation as specified in the configuration.

        Args:
            jira_project (str): The key of the Jira project where the issue will be created.
            jira_issue (Dict[str, Any]): A dictionary containing the fields and values for the new Jira issue.
            epic_key (Optional[str], optional): The key of the epic to link the new issue to. Defaults to None.
            parent_key (Optional[str], optional): The key of the parent issue for sub-tasks. Defaults to None.

        Returns:
            Dict[str, Any]: The response from the Jira API after creating the issue.

        Example:
            jira_issue = {
                'summary': 'New Issue',
                'description': 'Description of the new issue',
                'issuetype': 'Task',
                'assignee': 'user',
                'priority': 'High'
            }
            jira_project = 'PROJECT_KEY'
            epic_key = 'EPIC_KEY'

            response = jira.create_new_jira_issue(jira_project, jira_issue, epic_key)
        '''
        # Build initial issue data excluding post-creation fields
        # The post-creation fields are not allowed to be set during the issue creation time
        initial_issue_data = self._build_issue_data(jira_project,
                                                    jira_issue,
                                                    self.post_creation_update_fields)
        # Setting the issue's project
        initial_issue_data['fields']['project'] = {'key': jira_project}

        # Set a link to epic if epic_key is provided and issuetype is not Sub-task
        if epic_key and jira_issue.get('issuetype') != 'Sub-task':
            initial_issue_data['fields'][self.custom_field_mapping['epicLink']] = epic_key
        # Handle sub-tasks by linking them to parent_key if provided
        elif jira_issue.get('issuetype') == 'Sub-task' and parent_key:
            initial_issue_data['fields']['parent'] = {'key': parent_key}

        # Send a request to create the issue
        response_data = self.send_request(api_type='issue',
                                          method='post',
                                          jira_request_data=initial_issue_data)
        issue_key = response_data['key']
        if issue_key:
            logging.debug(f'Issue {issue_key} successfully created')
        else:
            raise ValueError(
                'Failed to retrieve issue key from the Jira response')

        # Prepare the update data for post-creation fields
        # The post-creation fields can be set after the issue is created
        fields_set_during_issue_creation = set(
            jira_issue.keys()) - set(self.post_creation_update_fields)
        update_data = self._build_issue_data(jira_project,
                                             jira_issue,
                                             exclude_fields=fields_set_during_issue_creation)
        if update_data['fields']:
            logging.debug('Update the issue with the post-creation fields')
            self.send_request(api_type='issue',
                              method='put',
                              issue_key=issue_key,
                              jira_request_data=update_data)

        if 'issuelinks' in jira_issue.keys():
            for link in jira_issue['issuelinks']:
                link_type = link['type'].get('name', 'Related')
                issue_parent_key = link['outwardIssue'].get('key', '')
            logging.debug(f'Requesting a "{link_type}" link between '
                          f'{issue_key} --> {issue_parent_key}')
            self.link_jira_issues(issue_key, issue_parent_key, link_type)

        return response_data

    def create_list_of_jira_issues(self,
                                   jira_project: str,
                                   jira_issues: Dict[str, Any],
                                   epic_key: Optional[str] = None,
                                   issue_parent_key: Optional[str] = None) -> None:
        '''
        Recursively create a list of Jira issues under a specific project and epic.
        Optionally link them to a parent issue.

        Args:
            jira_project (str): The key of the Jira project where the issues will be created.
            jira_issues (Dict[str, Any]): A dictionary containing the fields and values for the new Jira issues.
            epic_key (Optional[str], optional): The key of the epic to link the new issues to. Defaults to None.
            issue_parent_key (Optional[str], optional): The key of the parent issue for sub-tasks. Defaults to None.
        '''
        for issue in jira_issues:
            logging.info(
                f'Creating a Jira Issue type {issue["issuetype"]}: \"{issue["summary"]}\"')
            issue_create_response = self.create_new_jira_issue(jira_project=jira_project,
                                                               jira_issue=issue,
                                                               epic_key=epic_key,
                                                               parent_key=issue_parent_key)
            issue_key = issue_create_response['key']
            if epic_key:
                logging.info(f'Issue created successfully under Epic {epic_key}: '
                             f'{self.jira_url}/browse/{issue_key}')
            else:
                logging.info(
                    f'Issue created successfully: {self.jira_url}/browse/{issue_key}')

            # Create a link if the issue is a child issue
            # This means that the issue is part of another issue's 'issues' list
            if issue_parent_key and issue['issuetype'] != 'Sub-task':
                link_type = issue.get('linkType', 'Related')
                logging.debug(f'Requesting a "{link_type}" link between '
                              f'{issue_key} --> {issue_parent_key}')
                self.link_jira_issues(issue_key, issue_parent_key, link_type)

            # Recursively create child issues if 'issues' key exists in the current issue
            if 'issues' in issue:
                self.create_list_of_jira_issues(
                    jira_project, issue['issues'], epic_key, issue_key)

    def create_epics_and_issues(self,
                                jira_project: str,
                                epics: List[str]) -> None:
        '''
        Create Jira epics and optionally their associated issues.

        Args:
            jira_project (str): Key of the Jira project where epics/issues will be created.
            epics (list): List of dictionaries containing details of epics and optionally issues.

        Raises:
            KeyError: If required keys are missing in the epics data structure.
        '''
        for epic in epics:
            try:
                logging.info(f'Creating a Jira Epic \"{epic["epicName"]}\"')
                epic_create_response = self.create_new_jira_issue(jira_project=jira_project,
                                                                  jira_issue=epic)
                epic_key = epic_create_response['key']
                logging.info(
                    f'Epic created successfully: {self.jira_url}/browse/{epic_key}')

                if 'issues' in epic:
                    self.create_list_of_jira_issues(
                        jira_project, epic['issues'], epic_key=epic_key)

            except KeyError as e:
                logging.error(
                    f'Failed to process epic: {e}. Ensure all required fields are provided.')
                raise e
