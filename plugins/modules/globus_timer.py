#!/usr/bin/python

DOCUMENTATION = r"""
---
module: globus_timer
short_description: Manage Globus Timers
description:
    - Create, update, or delete Globus Timers
    - Schedule automated transfers and workflows
    - Supports both one-time and recurring timers
version_added: "1.0.0"
author:
    - Ansible Globus Module Contributors
options:
    name:
        description: Name/label for the timer
        required: true
        type: str
    timer_id:
        description: ID of existing timer (for updates/deletion)
        required: false
        type: str
    schedule:
        description: Schedule specification for the timer
        required: false
        type: dict
        suboptions:
            type:
                description: Type of schedule (once, recurring)
                type: str
                choices: ['once', 'recurring']
                default: 'once'
            datetime:
                description: ISO 8601 datetime for one-time execution
                type: str
            interval_seconds:
                description: Interval in seconds for recurring timers
                type: int
            interval_minutes:
                description: Interval in minutes for recurring timers
                type: int
            interval_hours:
                description: Interval in hours for recurring timers
                type: int
            interval_days:
                description: Interval in days for recurring timers
                type: int
    callback_url:
        description: URL to call when timer fires
        required: false
        type: str
    callback_body:
        description: JSON body to send to callback URL
        required: false
        type: dict
    scope:
        description: Scope required for timer operation
        required: false
        type: str
    start:
        description: Start datetime (ISO 8601) for recurring timers
        required: false
        type: str
    stop_after:
        description: Stop datetime (ISO 8601) for recurring timers
        required: false
        type: str
    stop_after_n:
        description: Number of executions before stopping
        required: false
        type: int
    state:
        description: Desired state of the timer
        required: false
        type: str
        choices: ['present', 'absent', 'active', 'inactive']
        default: 'present'
extends_documentation_fragment:
    - globus_auth
"""

EXAMPLES = r"""
- name: Create one-time timer
  globus_timer:
    name: "One-time data transfer"
    schedule:
      type: once
      datetime: "2025-12-31T23:59:59Z"
    callback_url: "https://transfer.api.globus.org/v0.10/transfer"
    callback_body:
      source_endpoint: "{{ source_ep }}"
      destination_endpoint: "{{ dest_ep }}"
      DATA:
        - source_path: "/data/"
          destination_path: "/backup/"
          recursive: true
    state: present

- name: Create recurring timer (every 24 hours)
  globus_timer:
    name: "Daily backup"
    schedule:
      type: recurring
      interval_hours: 24
    start: "2025-01-01T00:00:00Z"
    callback_url: "https://transfer.api.globus.org/v0.10/transfer"
    callback_body:
      source_endpoint: "{{ source_ep }}"
      destination_endpoint: "{{ dest_ep }}"
      DATA:
        - source_path: "/data/"
          destination_path: "/backup/"
          recursive: true
    state: present

- name: Create timer with stop conditions
  globus_timer:
    name: "Weekly sync (10 times)"
    schedule:
      type: recurring
      interval_days: 7
    start: "2025-01-01T00:00:00Z"
    stop_after_n: 10
    callback_url: "https://transfer.api.globus.org/v0.10/transfer"
    callback_body:
      source_endpoint: "{{ source_ep }}"
      destination_endpoint: "{{ dest_ep }}"
      DATA:
        - source_path: "/data/"
          destination_path: "/sync/"
          recursive: true
    state: present

- name: Pause a timer
  globus_timer:
    name: "Daily backup"
    state: inactive

- name: Resume a timer
  globus_timer:
    name: "Daily backup"
    state: active

- name: Delete a timer
  globus_timer:
    name: "Old timer"
    state: absent
"""

RETURN = r"""
timer_id:
    description: ID of the created/managed timer
    type: str
    returned: when state=present
name:
    description: Name of the timer
    type: str
    returned: always
status:
    description: Current status of the timer (active/inactive)
    type: str
    returned: when state=present
schedule:
    description: Timer schedule information
    type: dict
    returned: when state=present
changed:
    description: Whether the timer was changed
    type: bool
    returned: always
"""

from datetime import UTC, datetime, timedelta

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.m1yag1.globus.plugins.module_utils.globus_common import (
    globus_argument_spec,
)
from ansible_collections.m1yag1.globus.plugins.module_utils.globus_sdk_client import (
    GlobusSDKClient,
)


def find_timer_by_name(api, name):
    """Find a timer by name using SDK."""
    try:
        response = api.timers_client.list_jobs()
        timers = (
            response.data.get("jobs", [])
            if hasattr(response, "data")
            else response.get("jobs", [])
        )

        for timer in timers:
            # Timers/Jobs have a 'name' field
            timer_name = timer.get("name")
            if timer_name == name:
                # Use job_id (normalize to timer_id for consistency)
                timer_id = timer.get("job_id") or timer.get("timer_id")
                full_timer = api.timers_client.get_job(timer_id)
                result = full_timer.data if hasattr(full_timer, "data") else full_timer

                # Normalize job_id to timer_id for consistent interface
                if "job_id" in result and "timer_id" not in result:
                    result["timer_id"] = result["job_id"]

                return result
        return None
    except Exception as e:
        api.handle_api_error(e, f"searching for timer '{name}'")


def parse_schedule(schedule_params, start=None, stop_after=None, stop_after_n=None):
    """Parse schedule parameters into timer schedule format."""
    if not schedule_params:
        return None

    schedule_type = schedule_params.get("type", "once")
    schedule = {"type": schedule_type}

    if schedule_type == "once":
        if "datetime" in schedule_params:
            schedule["datetime"] = schedule_params["datetime"]
        else:
            # Default to 1 hour from now
            future_time = datetime.utcnow() + timedelta(hours=1)
            schedule["datetime"] = future_time.isoformat() + "Z"

    elif schedule_type == "recurring":
        # Calculate interval in seconds
        interval = 0
        if "interval_seconds" in schedule_params:
            interval = schedule_params["interval_seconds"]
        elif "interval_minutes" in schedule_params:
            interval = schedule_params["interval_minutes"] * 60
        elif "interval_hours" in schedule_params:
            interval = schedule_params["interval_hours"] * 3600
        elif "interval_days" in schedule_params:
            interval = schedule_params["interval_days"] * 86400

        if interval == 0:
            raise ValueError("Recurring timer must specify an interval")

        schedule["interval_seconds"] = interval

        if start:
            schedule["start"] = start
        if stop_after:
            schedule["end"] = stop_after
        if stop_after_n:
            schedule["stop_after_n"] = stop_after_n

    return schedule


def create_timer(api, params):
    """Create a new timer using SDK."""
    try:
        from datetime import datetime

        from globus_sdk import TimerJob

        # Parse schedule into start time and interval
        schedule_params = params.get("schedule", {})
        schedule_type = schedule_params.get("type", "once")

        # Determine start time
        start = params.get("start")
        if not start:
            # If no start specified, use current time for recurring, or datetime from schedule for once
            if schedule_type == "once" and schedule_params.get("datetime"):
                start = schedule_params["datetime"]
            else:
                start = datetime.now(UTC).isoformat()

        # Determine interval (None for one-time timers)
        interval = None
        if schedule_type == "recurring":
            if "interval_seconds" in schedule_params:
                interval = schedule_params["interval_seconds"]
            elif "interval_minutes" in schedule_params:
                interval = schedule_params["interval_minutes"] * 60
            elif "interval_hours" in schedule_params:
                interval = schedule_params["interval_hours"] * 3600
            elif "interval_days" in schedule_params:
                interval = schedule_params["interval_days"] * 86400
            else:
                # Default to 24 hours if no interval specified
                interval = 86400

        # Build timer job using SDK's TimerJob class
        job_kwargs = {
            "callback_url": params.get("callback_url"),
            "callback_body": params.get("callback_body", {}),
            "start": start,
            "interval": interval,
        }

        if params.get("name"):
            job_kwargs["name"] = params["name"]
        if params.get("stop_after"):
            job_kwargs["stop_after"] = params["stop_after"]
        if params.get("stop_after_n"):
            job_kwargs["stop_after_n"] = params["stop_after_n"]
        if params.get("scope"):
            job_kwargs["scope"] = params["scope"]

        timer_job = TimerJob(**job_kwargs)
        response = api.timers_client.create_job(data=timer_job)
        result = response.data if hasattr(response, "data") else response

        # Normalize job_id to timer_id for consistent interface
        if "job_id" in result and "timer_id" not in result:
            result["timer_id"] = result["job_id"]

        return result

    except Exception as e:
        api.handle_api_error(e, "creating timer")


def update_timer(api, timer_id, params):
    """Update an existing timer using SDK."""
    try:
        update_data = {}

        # Parse schedule if provided
        if params.get("schedule"):
            schedule = parse_schedule(
                params.get("schedule"),
                params.get("start"),
                params.get("stop_after"),
                params.get("stop_after_n"),
            )
            update_data["schedule"] = schedule

        # Update callback if provided
        if params.get("callback_url"):
            update_data["callback_url"] = params["callback_url"]

        if params.get("callback_body"):
            update_data["callback_body"] = params["callback_body"]

        if update_data:
            response = api.timers_client.update_timer(timer_id, timer=update_data)
            return response.data if hasattr(response, "data") else response

        return None
    except Exception as e:
        api.handle_api_error(e, f"updating timer {timer_id}")


def pause_timer(api, timer_id):
    """Pause/deactivate a timer using SDK."""
    try:
        # Pause by updating the job to inactive state
        response = api.timers_client.update_job(timer_id, data={"inactive": True})
        return response.data if hasattr(response, "data") else response
    except Exception as e:
        api.handle_api_error(e, f"pausing timer {timer_id}")


def resume_timer(api, timer_id):
    """Resume/activate a timer using SDK."""
    try:
        response = api.timers_client.update_job(timer_id, data={"inactive": False})
        return response.data if hasattr(response, "data") else response
    except Exception as e:
        api.handle_api_error(e, f"resuming timer {timer_id}")


def delete_timer(api, timer_id):
    """Delete a timer using SDK."""
    try:
        api.timers_client.delete_job(timer_id)
        return True
    except Exception as e:
        api.handle_api_error(e, f"deleting timer {timer_id}")


def main():
    argument_spec = globus_argument_spec()
    argument_spec.update(
        name={"type": "str", "required": True},
        timer_id={"type": "str"},
        schedule={"type": "dict"},
        callback_url={"type": "str"},
        callback_body={"type": "dict"},
        scope={"type": "str"},
        start={"type": "str"},
        stop_after={"type": "str"},
        stop_after_n={"type": "int"},
        state={
            "type": "str",
            "choices": ["present", "absent", "active", "inactive"],
            "default": "present",
        },
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    api = GlobusSDKClient(module, required_services=["timers"])

    name = module.params["name"]
    state = module.params["state"]
    timer_id = module.params.get("timer_id")

    # Find existing timer
    if timer_id:
        try:
            response = api.timers_client.get_timer(timer_id)
            existing_timer = response.data if hasattr(response, "data") else response
        except Exception:
            existing_timer = None
    else:
        existing_timer = find_timer_by_name(api, name)

    if state == "present":
        if existing_timer:
            # Update existing timer
            changed = False
            timer_id = existing_timer["timer_id"]

            # Update timer if schedule or callback changed
            if (
                module.params.get("schedule") or module.params.get("callback_url")
            ) and not module.check_mode:
                update_result = update_timer(api, timer_id, module.params)
                if update_result:
                    changed = True

            module.exit_json(
                changed=changed,
                timer_id=timer_id,
                name=name,
                status=existing_timer.get("status", "active"),
                schedule=existing_timer.get("schedule"),
            )
        else:
            # Create new timer
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            timer = create_timer(api, module.params)
            timer_id = timer["timer_id"]

            module.exit_json(
                changed=True,
                timer_id=timer_id,
                name=name,
                status=timer.get("status", "active"),
                schedule=timer.get("schedule"),
            )

    elif state == "absent":
        if existing_timer:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            delete_timer(api, existing_timer["timer_id"])
            module.exit_json(changed=True, name=name)
        else:
            module.exit_json(changed=False, name=name)

    elif state == "inactive":
        if existing_timer:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            pause_timer(api, existing_timer["timer_id"])
            module.exit_json(changed=True, name=name, status="inactive")
        else:
            module.fail_json(msg=f"Timer '{name}' not found")

    elif state == "active":
        if existing_timer:
            if module.check_mode:
                module.exit_json(changed=True, name=name)

            resume_timer(api, existing_timer["timer_id"])
            module.exit_json(changed=True, name=name, status="active")
        else:
            module.fail_json(msg=f"Timer '{name}' not found")


if __name__ == "__main__":
    main()
