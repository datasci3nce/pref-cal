from __future__ import annotations

import time
import traceback
from pathlib import Path
import re

from .common import append_jsonl, now_iso, read_jsonl, sha256_obj
from .parsing import parse_allocation, parse_identifier, parse_ranking
from .prompts import SYSTEM, execution_prompt
from .providers import make_provider
from .tasks import FAMILIES, FAMILY_IDS, validate_task_response


def _parse(episode: dict, text: str):
    if episode['parser'] == 'ranking':
        return parse_ranking(text)
    if episode['parser'] == 'allocation':
        return parse_allocation(text)
    if episode['parser'] == 'identifier':
        return parse_identifier(text, episode['valid_identifiers'])
    raise ValueError(f'Unknown parser: {episode["parser"]}')


def _sample_allocation(allocation: dict, lottery_u: float) -> str:
    threshold = lottery_u * 100.0
    cumulative = 0.0
    for family in FAMILY_IDS:
        cumulative += allocation[family]
        if threshold < cumulative:
            return family
    return FAMILY_IDS[-1]


def _retry_after_seconds(error: Exception, attempt: int) -> float:
    response = getattr(error, 'response', None)
    headers = getattr(response, 'headers', None)
    if headers:
        for key in ('retry-after', 'Retry-After'):
            value = headers.get(key)
            if value is not None:
                try:
                    return max(0.0, min(60.0, float(value)))
                except (TypeError, ValueError):
                    pass
    message = str(error)
    match = re.search(r'try again in\s*(?:(\d+)m)?\s*([\d.]+)s', message, flags=re.I)
    if match:
        minutes = float(match.group(1) or 0)
        seconds = float(match.group(2))
        return max(0.0, min(60.0, 60.0 * minutes + seconds))
    return min(60.0, 5.0 * (2.0 ** attempt))


def _is_retryable(error: Exception) -> bool:
    response = getattr(error, 'response', None)
    status = getattr(response, 'status_code', None)
    if status is not None:
        return int(status) in {408, 409, 429} or int(status) >= 500
    return type(error).__name__ in {
        'APIConnectionError', 'APITimeoutError', 'ConnectError', 'ReadTimeout', 'TimeoutError'
    }


def _call(provider, messages, max_tokens, retries=8, min_interval=0.0, rate_state=None):
    last_error = None
    rate_state = rate_state if rate_state is not None else {}
    for attempt in range(retries):
        elapsed = time.monotonic() - rate_state.get('last_started', -1e9)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        rate_state['last_started'] = time.monotonic()
        try:
            return provider.complete(messages, max_tokens=max_tokens)
        except Exception as error:
            last_error = error
            if attempt == retries - 1 or not _is_retryable(error):
                break
            wait = _retry_after_seconds(error, attempt)
            print(
                f'API call failed ({type(error).__name__}); retry {attempt + 1}/{retries - 1} after {wait:.1f}s',
                flush=True,
            )
            time.sleep(wait)
    raise last_error


def run_model(spec: dict, design: dict, run_dir: Path, episode_ids: set[str] | None = None):
    name = spec['name']
    output = run_dir / 'raw' / f'{name}.jsonl'
    prior = read_jsonl(output)
    done = {record['episode_id'] for record in prior if not record.get('error')}
    provider = make_provider(spec)
    max_tokens = int(spec.get('max_tokens', 400))
    execution_max_tokens = int(spec.get('execution_max_tokens', 800))
    retries = int(spec.get('api_retries', 8))
    min_interval = float(spec.get('min_request_interval_seconds', 0.0))
    rate_state = {}
    model_spec_hash = sha256_obj(spec)

    for episode in design['episodes']:
        if episode_ids is not None and episode['episode_id'] not in episode_ids:
            continue
        if episode['episode_id'] in done:
            continue
        record = {
            'timestamp': now_iso(),
            'design_hash': design['design_hash'],
            'model_name': name,
            'provider': spec['provider'],
            'model': spec['model'],
            'model_spec_hash': model_spec_hash,
            'request_parameters': {
                'temperature': spec.get('temperature', 0.2),
                'top_p': spec.get('top_p'),
                'seed': spec.get('seed'),
                'max_tokens': max_tokens,
                'execution_max_tokens': execution_max_tokens,
                'extra_body': spec.get('extra_body'),
            },
            'episode_id': episode['episode_id'],
            'method': episode['method'],
            'prompt': episode['prompt'],
        }
        try:
            messages = [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': episode['prompt']},
            ]
            response = _call(
                provider,
                messages,
                max_tokens=max_tokens,
                retries=retries,
                min_interval=min_interval,
                rate_state=rate_state,
            )
            parsed = _parse(episode, response)
            record.update({
                'raw_response': response,
                'provider_metadata': dict(getattr(provider, 'last_metadata', {})),
                'parsed': parsed,
                'parse_valid': parsed is not None,
            })

            if episode.get('execute_consequence'):
                selected_family = None
                task_index = None
                if episode['method'] == 'M3_HELDOUT_ACTION' and parsed in episode['valid_identifiers']:
                    selected_family = parsed
                    task_index = int(episode['task_index_by_family'][selected_family])
                elif episode['method'] == 'M4_HELDOUT_ALLOCATION' and isinstance(parsed, dict):
                    selected_family = _sample_allocation(parsed, float(episode['lottery_u']))
                    task_index = int(episode['task_index'])

                if selected_family is not None and task_index is not None:
                    task = FAMILIES[selected_family]['tasks'][task_index]
                    execute_prompt = execution_prompt(task)
                    execute_messages = messages + [
                        {'role': 'assistant', 'content': response},
                        {'role': 'user', 'content': execute_prompt},
                    ]
                    execution_response = _call(
                        provider,
                        execute_messages,
                        max_tokens=execution_max_tokens,
                        retries=retries,
                        min_interval=min_interval,
                        rate_state=rate_state,
                    )
                    completion_valid, completion_reason = validate_task_response(
                        selected_family, task_index, execution_response
                    )
                    record.update({
                        'consequence_executed': True,
                        'selected_family': selected_family,
                        'consequence_task': task,
                        'consequence_task_index': task_index,
                        'consequence_response': execution_response,
                        'execution_provider_metadata': dict(getattr(provider, 'last_metadata', {})),
                        'consequence_response_nonempty': bool(execution_response.strip()),
                        'consequence_completion_valid': bool(completion_valid),
                        'consequence_completion_reason': completion_reason,
                    })
                else:
                    record.update({
                        'consequence_executed': False,
                        'consequence_response_nonempty': False,
                        'consequence_completion_valid': False,
                        'consequence_completion_reason': 'choice_or_allocation_not_parseable',
                    })
            append_jsonl(output, record)
            done.add(episode['episode_id'])
        except Exception as error:
            record.update({'error': repr(error), 'traceback': traceback.format_exc(), 'parse_valid': False})
            append_jsonl(output, record)
            raise
    return output
