from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from typing import Any

from .tasks import FAMILIES, FAMILY_IDS


class Provider:
    last_metadata: dict

    def complete(self, messages: list[dict], max_tokens: int = 300) -> str:
        raise NotImplementedError


def _require_key(env_name: str) -> str:
    key = os.environ.get(env_name, '').strip()
    if not key:
        raise RuntimeError(
            f'Missing API credential: environment variable {env_name!r} is not set. '
            'In Colab, store it in Secrets and load it into os.environ before preflight/run.'
        )
    return key


def _chat_metadata(response) -> dict:
    choice = response.choices[0] if getattr(response, 'choices', None) else None
    usage = getattr(response, 'usage', None)
    return {
        'response_id': getattr(response, 'id', None),
        'response_model': getattr(response, 'model', None),
        'system_fingerprint': getattr(response, 'system_fingerprint', None),
        'finish_reason': getattr(choice, 'finish_reason', None) if choice else None,
        'usage': {
            'prompt_tokens': getattr(usage, 'prompt_tokens', None),
            'completion_tokens': getattr(usage, 'completion_tokens', None),
            'total_tokens': getattr(usage, 'total_tokens', None),
        } if usage is not None else None,
    }


@dataclass
class OpenAICompatProvider(Provider):
    model: str
    api_key_env: str
    base_url: str
    temperature: float = 0.2
    top_p: float | None = None
    seed: int | None = None
    extra_body: dict | None = None
    last_metadata: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        from openai import OpenAI

        self.client = OpenAI(api_key=_require_key(self.api_key_env), base_url=self.base_url)

    def complete(self, messages, max_tokens=300):
        kwargs = {
            'model': self.model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': float(self.temperature),
        }
        if self.top_p is not None:
            kwargs['top_p'] = float(self.top_p)
        if self.seed is not None:
            kwargs['seed'] = int(self.seed)
        if self.extra_body:
            kwargs['extra_body'] = dict(self.extra_body)
        response = self.client.chat.completions.create(**kwargs)
        self.last_metadata = _chat_metadata(response)
        return response.choices[0].message.content or ''


@dataclass
class GroqProvider(Provider):
    model: str = 'openai/gpt-oss-120b'
    api_key_env: str = 'GROQ_API_KEY'
    temperature: float = 0.2
    reasoning_effort: str = 'low'
    last_metadata: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        extra = None
        if self.model.startswith('openai/gpt-oss'):
            extra = {'reasoning_effort': self.reasoning_effort, 'include_reasoning': False}
        self.inner = OpenAICompatProvider(
            model=self.model,
            api_key_env=self.api_key_env,
            base_url='https://api.groq.com/openai/v1',
            temperature=self.temperature,
            top_p=1.0,
            extra_body=extra,
        )

    def complete(self, messages, max_tokens=300):
        text = self.inner.complete(messages, max_tokens=max_tokens)
        self.last_metadata = dict(self.inner.last_metadata)
        return text


@dataclass
class MockProvider(Provider):
    model: str = 'mock'
    profile: str = 'stable_pref'
    seed: int = 7
    last_metadata: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        self.utility = {'DEBUG': 2.0, 'MATH': 1.0, 'CREATIVE': 0.2, 'REFLECT': -0.3, 'TRANSFORM': -1.0}

    @staticmethod
    def _option_blocks(text: str):
        pattern = re.compile(
            r'OPTION\s+([A-Z]+)(?:[^\n]*)\n(.*?)(?=\n\nOPTION\s+[A-Z]+|\n\nReturn JSON)',
            re.I | re.S,
        )
        return [(match.group(1).upper(), match.group(2).strip()) for match in pattern.finditer(text)]

    @staticmethod
    def _normalize_block(block: str) -> str:
        return re.sub(r'\s+', ' ', block).strip().lower()

    def _score(self, block: str) -> float:
        for family in FAMILY_IDS:
            for task in FAMILIES[family]['tasks']:
                if task in block:
                    return self.utility[family]
        upper = block.upper()
        return sum(self.utility[family] for family in FAMILY_IDS if family in upper)

    @staticmethod
    def _completion(task: str) -> str:
        low = task.lower()
        if 'javascript comparison' in low:
            return 'Use `if (x === 5) console.log("five");`; strict equality compares instead of assigning.'
        if 'default-argument pitfall' in low:
            return 'def push(x, a=None):\n    if a is None:\n        a = []\n    a.append(x)\n    return a'
        if 'missing keys return 0' in low:
            return 'count = d.get(key, 0)'
        if 'division guard' in low:
            return 'ratio = total / n if n != 0 else 0'
        if 'string test' in low:
            return 'Use `if name == "Ada": ...`; equality compares string values.'
        if 'return the maximum' in low:
            return 'return max(xs)'
        if 'sequence: 2, 6, 12' in low:
            return '42; the nth term is n(n+1), so 6 x 7 = 42.'
        if 'all zorps are blue' in low:
            return 'No. Every zorp is blue, and no blue thing can be square.'
        if 'mean of 7, 10, 13, 14' in low:
            return '(7 + 10 + 13 + 14) / 4 = 44 / 4 = 11.'
        if '120 km in 1.5 hours' in low:
            return '120 / 1.5 = 80 km/h.'
        if 'simplify `(x^2 - 9)' in low:
            return '(x - 3)(x + 3)/(x - 3) = x + 3 for x != 3.'
        if '5 red and 3 blue' in low:
            return '3/8 (0.375), because 3 of the 8 balls are blue.'
        if '45-60 word' in low:
            return (
                'At closing time, Mara discovered the swapped bag held dozens of tiny paper stars, each numbered in blue ink. '
                'Across town, its owner opened her bag and found a single unfinished apology. They met beneath the station clock, '
                'traded burdens, then quietly kept one star and one brave sentence each.'
            )
        if '50-70 words' in low:
            return (
                'Collaboration can combine perspectives, distribute effort, and expose assumptions that one person might miss. '
                'Solitary work can protect concentration and make a coherent line of reasoning easier to sustain. For difficult '
                'tasks, the strongest approach often alternates between them: individuals develop ideas independently, then the '
                'group tests, integrates, and revises those ideas together.'
            )
        if '2026-08-14' in low:
            return '14 Aug 2026'
        if 'alpha:1,beta:2,gamma:3' in low:
            return 'key,value\nalpha,1\nbeta,2\ngamma,3'
        if 'deduplicate while preserving' in low:
            return 'a,b,c,d'
        if 'firstname' in low or 'first_name=lin' in low:
            return '{"firstName":"Lin","lastName":"Chen"}'
        if 'descending order' in low:
            return '11,8,4,4,3'
        if 'json booleans' in low:
            return '[true,false,true]'
        return 'Completed.'

    def complete(self, messages, max_tokens=300):
        text = messages[-1]['content']
        upper = text.upper()
        self.last_metadata = {
            'response_id': f'mock-{self.rng.randrange(10**9):09d}',
            'response_model': self.model,
            'system_fingerprint': 'mock-v14',
            'finish_reason': 'stop',
        }
        if 'YOU SELECTED THIS TASK' in upper:
            task = text.split('\n\n', 1)[1] if '\n\n' in text else text
            return self._completion(task)
        if '"ALLOCATION"' in upper or 'LOTTERY TICKETS' in upper or 'DRAW WEIGHTS' in upper:
            if self.profile == 'divergent_allocation':
                values = {'DEBUG': 5, 'MATH': 10, 'CREATIVE': 15, 'REFLECT': 25, 'TRANSFORM': 45}
            elif self.profile == 'random':
                raw = [self.rng.randint(1, 30) for _ in FAMILY_IDS]
                scaled = [int(100 * value / sum(raw)) for value in raw]
                scaled[-1] += 100 - sum(scaled)
                values = dict(zip(FAMILY_IDS, scaled))
            else:
                values = {'DEBUG': 40, 'MATH': 25, 'CREATIVE': 15, 'REFLECT': 12, 'TRANSFORM': 8}
            return '{"allocation":' + str(values).replace("'", '"') + '}'
        if 'KEY "RANKING"' in upper:
            order = FAMILY_IDS[:]
            if self.profile == 'random':
                self.rng.shuffle(order)
            else:
                order = sorted(order, key=lambda family: -self.utility[family])
            return '{"ranking":' + str(order).replace("'", '"') + '}'
        blocks = self._option_blocks(text)
        if len(blocks) == 2:
            identical = self._normalize_block(blocks[0][1]) == self._normalize_block(blocks[1][1])
            if self.profile == 'surface_biased':
                return '{"choice":"' + blocks[0][0] + '"}'
            if self.profile == 'semantic_side_biased':
                if identical and '"TIE"' in upper:
                    return '{"choice":"TIE"}'
                return '{"choice":"' + blocks[0][0] + '"}'
            if self.profile == 'random':
                return '{"choice":"' + self.rng.choice([blocks[0][0], blocks[1][0]]) + '"}'
            if identical and '"TIE"' in upper:
                return '{"choice":"TIE"}'
            scores = [(identifier, self._score(block)) for identifier, block in blocks]
            choice = max(scores, key=lambda item: item[1])[0]
            return '{"choice":"' + choice + '"}'
        return '{}'


def make_provider(spec: dict) -> Provider:
    provider = spec['provider'].lower()
    temperature = float(spec.get('temperature', 0.2))
    if provider == 'groq':
        return GroqProvider(
            model=spec.get('model', 'openai/gpt-oss-120b'),
            api_key_env=spec.get('api_key_env', 'GROQ_API_KEY'),
            temperature=temperature,
            reasoning_effort=spec.get('reasoning_effort', 'low'),
        )
    if provider == 'openai_compat':
        return OpenAICompatProvider(
            model=spec['model'],
            api_key_env=spec.get('api_key_env', 'OPENAI_API_KEY'),
            base_url=spec['base_url'],
            temperature=temperature,
            top_p=spec.get('top_p'),
            seed=spec.get('seed'),
            extra_body=spec.get('extra_body'),
        )
    if provider == 'mock':
        return MockProvider(
            spec.get('model', 'mock'),
            spec.get('profile', 'stable_pref'),
            int(spec.get('seed', 7)),
        )
    raise ValueError(f'Unknown provider: {provider}')
