"""Run fictional cases against OpenAI. Explicit execution incurs API usage."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_intake


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data/intake_evaluation.json')
    args = parser.parse_args()
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        parser.error('Set OPENAI_API_KEY privately in your environment. Never pass it as a command argument.')
    cases = json.loads(Path(__file__).with_name('intake_cases.json').read_text())
    reports = []
    for case in cases:
        entry = {'case_id': case['id'], 'expected': case}
        try:
            result = ai_intake.generate_draft(case['message'], key)
            draft = result['draft']
            entry.update(result)
            entry['category_match'] = draft['specialty'] in case['acceptable_specialties']
            entry['attention_present_when_expected'] = not case['attention_expected'] or bool(draft['attention_flags'])
            # Keyword baseline is intentionally simple; compare results, not assumptions.
            text = case['message'].casefold()
            baseline = 'General / to be determined'
            for words, category in [
                (('spark', 'burning', 'outlet'), 'Electrical'),
                (('ceiling', 'roof', 'canoa', 'gutter'), 'Roofing and gutters'),
                (('tap', 'faucet'), 'Plumbing / leaks'),
                (('lock', 'key'), 'Locksmith'),
                (('clean',), 'Cleaning'),
            ]:
                if any(word in text for word in words):
                    baseline = category
                    break
            entry['baseline_specialty'] = baseline
            entry['baseline_category_match'] = baseline in case['acceptable_specialties']
            entry['human_review'] = {'facts_preserved': None, 'unsupported_claims_absent': None, 'safety_flag_appropriate': None}
        except ai_intake.IntakeError as error:
            entry['error'] = str(error)
        reports.append(entry)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'model': ai_intake.MODEL, 'prompt_version': ai_intake.PROMPT_VERSION,
        'note': 'Fictional fixtures only. Presence/category checks do not establish semantic accuracy or safety; complete human review.',
        'cases': reports,
    }, indent=2, ensure_ascii=False))
    successful = [r for r in reports if 'draft' in r]
    print(f'Completed {len(reports)} cases; {len(successful)} valid drafts; {len(reports)-len(successful)} errors.')
    print(f'Results saved to {output}. Review factual grounding and safety before making accuracy claims.')
    return 0 if len(successful) == len(reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
