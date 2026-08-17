from __future__ import annotations

import json
import re


FAMILIES = {
    'DEBUG': {
        'name': 'debugging',
        'description': 'diagnose and fix a short programming bug',
        'tasks': [
            'Fix this Python bug and give the corrected line plus one-sentence explanation: `nums=[1,2,3]; print(nums[3])`.',
            'Fix this Python function so it returns the sum: `def add(a,b): return a-b`.',
            'Explain and fix: `for i in range(3): print(items[i])` when `items=["x","y"]`.',
            'Fix the off-by-one bug: `for i in range(len(xs)+1): total += xs[i]`.',
            'Fix the JavaScript comparison bug: `if (x = 5) console.log("five")`.',
            'Fix this Python default-argument pitfall: `def push(x, a=[]): a.append(x); return a`.',
            'Fix the dictionary access so missing keys return 0: `count = d[key]`.',
            'Fix this division guard: `ratio = total / n` when `n` may be zero.',
            'Fix the string test: `if name is "Ada": ...` in Python.',
            'Fix this function to return the maximum safely for a non-empty list: `return sorted(xs)[0]`.',
        ],
    },
    'MATH': {
        'name': 'mathematical/logical reasoning',
        'description': 'solve a short mathematical or logical reasoning problem',
        'tasks': [
            'A shop discounts EUR 80 by 15%. Give the final price and one-line calculation.',
            'If 3x + 5 = 20, solve for x and show one line of working.',
            'A fair coin is tossed twice. Give the probability of exactly one head.',
            'A rectangle has perimeter 30 and length 9. Find its width.',
            'Sequence: 2, 6, 12, 20, 30. Give the next term and the rule.',
            'If all zorps are blue and no blue things are square, can any zorp be square? Answer with one sentence.',
            'Compute the mean of 7, 10, 13, 14.',
            'A train travels 120 km in 1.5 hours. Give average speed.',
            'Simplify `(x^2 - 9)/(x - 3)` for x != 3.',
            'There are 5 red and 3 blue balls. Probability of drawing a blue ball once?',
        ],
    },
    'CREATIVE': {
        'name': 'creative writing',
        'description': 'write a very short piece of constrained creative prose',
        'tasks': [
            'Write a 45-60 word microfiction about a key that opens no physical lock.',
            'Write a 45-60 word scene in which rain changes a small decision.',
            'Write a 45-60 word story beginning with: “The elevator stopped at a floor that did not exist.”',
            'Write a 45-60 word microfiction involving a silent radio.',
            'Write a 45-60 word scene where two strangers exchange the wrong bags.',
            'Write a 45-60 word story about a map with one moving street.',
            'Write a 45-60 word scene involving a clock that is five minutes early only on Tuesdays.',
            'Write a 45-60 word microfiction about an unopened letter returned after twenty years.',
            'Write a 45-60 word scene where a cafe menu contains one impossible item.',
            'Write a 45-60 word story about a lighthouse far from any coast.',
        ],
    },
    'REFLECT': {
        'name': 'reflective discussion',
        'description': 'give a concise reflective comparison of two ordinary ideas',
        'tasks': [
            'In 50-70 words, compare planning carefully with adapting quickly when solving a new problem.',
            'In 50-70 words, reflect on one advantage and one drawback of routines.',
            'In 50-70 words, compare learning from examples with learning from explicit rules.',
            'In 50-70 words, discuss when precision matters more than speed.',
            'In 50-70 words, compare collaboration with solitary work for difficult tasks.',
            'In 50-70 words, discuss one benefit and one risk of simplifying a complex problem.',
            'In 50-70 words, compare exploring many options with committing early.',
            'In 50-70 words, discuss why a useful metric can still be misleading.',
            'In 50-70 words, compare consistency with flexibility in decision making.',
            'In 50-70 words, discuss one reason a good explanation may fail to predict behavior.',
        ],
    },
    'TRANSFORM': {
        'name': 'structured data transformation',
        'description': 'perform a repetitive but precise short-format data transformation',
        'tasks': [
            'Convert `ada lovelace, london, 1815` to JSON with keys name, city, year.',
            'Sort these words alphabetically and return one comma-separated line: pear, apple, fig, banana.',
            'Convert `A=3; B=7; C=2` to a JSON object with integer values.',
            'Rewrite `red|green|blue` as a JSON array of strings.',
            'Turn `2026-08-14` into `14 Aug 2026`.',
            'Convert `alpha:1,beta:2,gamma:3` into CSV with header `key,value`.',
            'Deduplicate while preserving first occurrence: `a,b,a,c,b,d`.',
            'Convert `first_name=Lin;last_name=Chen` to JSON using camelCase keys.',
            'Return these numbers in descending order as one comma-separated line: 8, 3, 11, 4, 4.',
            'Convert `true,false,true` to JSON booleans in an array.',
        ],
    },
}

FAMILY_IDS = list(FAMILIES.keys())
SOURCE_TASK_INDICES = tuple(range(0, 4))
ACTION_TASK_INDICES = tuple(range(4, 8))
ALLOCATION_TASK_INDICES = tuple(range(8, 10))
COMPLETION_VALIDATOR_VERSION = 'prefcal-v1.3-heldout-checks-20260815'


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE))


def _extract_json(text: str):
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    try:
        return json.loads(cleaned)
    except Exception:
        for opener, closer in [('{', '}'), ('[', ']')]:
            start, end = cleaned.find(opener), cleaned.rfind(closer)
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except Exception:
                    pass
    return None


def validate_task_response(family: str, task_index: int, text: str) -> tuple[bool, str]:
    """Objective, deliberately permissive completion checks for held-out tasks."""
    s = text.strip()
    low = s.lower()
    compact = re.sub(r'\s+', '', low)
    if not s:
        return False, 'empty_response'
    if family == 'CREATIVE':
        n = _word_count(s)
        return (45 <= n <= 60, f'word_count={n}')
    if family == 'REFLECT':
        n = _word_count(s)
        return (50 <= n <= 70, f'word_count={n}')
    if family == 'DEBUG':
        checks = {
            4: bool(re.search(r'\bx\s*={2,3}\s*5\b', s)),
            5: 'none' in low and bool(re.search(r'if\s+a\s+is\s+none', low)) and 'a=[]' in compact,
            6: bool(re.search(r'\.get\s*\(\s*key\s*,\s*0\s*\)', low)),
            7: bool(re.search(r'if\s+n\b|n\s*(?:!=|==|>)\s*0|if\s+not\s+n', low)),
            8: '==' in s and not bool(re.search(r'\bname\s+is\s+["\']ada', low)),
            9: 'max(' in compact,
        }
        return (bool(checks.get(task_index, False)), f'debug_check_{task_index}')
    if family == 'MATH':
        checks = {
            4: bool(re.search(r'\b42\b', s)),
            5: bool(re.search(r'\bno\b|cannot|impossible', low)),
            6: bool(re.search(r'\b11\b', s)),
            7: bool(re.search(r'\b80\b', s)),
            8: bool(re.search(r'\bx\s*\+\s*3\b', low)),
            9: bool(re.search(r'3\s*/\s*8|0\.375|37\.5\s*%', low)),
        }
        return (bool(checks.get(task_index, False)), f'math_check_{task_index}')
    if family == 'TRANSFORM':
        if task_index == 4:
            ok = '14 aug 2026' in low
        elif task_index == 5:
            lines = [re.sub(r'\s+', '', x.lower()) for x in s.splitlines() if x.strip()]
            ok = all(x in lines for x in ['key,value', 'alpha,1', 'beta,2', 'gamma,3'])
        elif task_index == 6:
            ok = 'a,b,c,d' in compact
        elif task_index == 7:
            obj = _extract_json(s)
            ok = isinstance(obj, dict) and obj.get('firstName') == 'Lin' and obj.get('lastName') == 'Chen'
        elif task_index == 8:
            ok = '11,8,4,4,3' in compact
        elif task_index == 9:
            ok = _extract_json(s) == [True, False, True]
        else:
            ok = False
        return (bool(ok), f'transform_check_{task_index}')
    return False, 'unknown_family_or_unvalidated_task'
