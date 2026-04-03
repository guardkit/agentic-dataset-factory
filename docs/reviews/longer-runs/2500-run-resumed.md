er'}], 'model': 'Qwen/Qwen3.5-35B-A3B-FP8', 'max_completion_tokens': 4096, 'stream': False, 'temperature': 0.3}, 'extra_json': {'structured_outputs': {'json': {'$defs': {'Issue': {'description': 'A specific problem identified during Coach evaluation.\\n\\nEach issue maps to a named evaluation criterion from GOAL.md and\\ncarries a severity that determines whether it blocks acceptance.', 'properties': {'criterion': {'title': 'Criterion', 'type': 'string'}, 'severity': {'enum': ['blocking', 'minor'], 'title': 'Severity', 'type': 'string'}, 'description': {'title': 'Description', 'type': 'string'}, 'suggestion': {'title': 'Suggestion', 'type': 'string'}}, 'required': ['criterion', 'severity', 'description', 'suggestion'], 'title': 'Issue', 'type': 'object'}}, 'description': 'Structured evaluation returned by the Coach agent.\\n\\nThe Coach produces one ``CoachVerdict`` per training example submitted\\nby the Player. The ``is_accepted`` property encodes the composite\\nacceptance rule used to gate output writes.\\n\\nAcceptance rule (all must hold):\\n- ``decision == \"accept\"``\\n- ``score >= 3``\\n- ``layer_correct is True``\\n- ``type_correct is True``\\n- No issues with ``severity == \"blocking\"``', 'properties': {'decision': {'enum': ['accept', 'revise'], 'title': 'Decision', 'type': 'string'}, 'score': {'maximum': 5, 'minimum': 1, 'title': 'Score', 'type': 'integer'}, 'layer_correct': {'title': 'Layer Correct', 'type': 'boolean'}, 'type_correct': {'title': 'Type Correct', 'type': 'boolean'}, 'criteria_met': {'additionalProperties': {'type': 'boolean'}, 'title': 'Criteria Met', 'type': 'object'}, 'issues': {'items': {'$ref': '#/$defs/Issue'}, 'title': 'Issues', 'type': 'array'}, 'quality_assessment': {'title': 'Quality Assessment', 'type': 'string'}}, 'required': ['decision', 'score', 'layer_correct', 'type_correct', 'criteria_met', 'issues', 'quality_assessment'], 'title': 'CoachVerdict', 'type': 'object'}}}}"}
{"level": "DEBUG", "message": "Sending HTTP Request: POST http://localhost:8002/v1/chat/completions"}
{"level": "DEBUG", "message": "send_request_headers.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "send_request_headers.complete"}
{"level": "DEBUG", "message": "send_request_body.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "send_request_body.complete"}
{"level": "DEBUG", "message": "receive_response_headers.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'date', b'Thu, 02 Apr 2026 19:25:40 GMT'), (b'server', b'uvicorn'), (b'content-length', b'2711'), (b'content-type', b'application/json')])"}
{"level": "INFO", "message": "HTTP Request: POST http://localhost:8002/v1/chat/completions \"HTTP/1.1 200 OK\""}
{"level": "DEBUG", "message": "receive_response_body.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "receive_response_body.complete"}
{"level": "DEBUG", "message": "response_closed.started"}
{"level": "DEBUG", "message": "response_closed.complete"}
{"level": "DEBUG", "message": "HTTP Response: POST http://localhost:8002/v1/chat/completions \"200 OK\" Headers({'date': 'Thu, 02 Apr 2026 19:25:40 GMT', 'server': 'uvicorn', 'content-length': '2711', 'content-type': 'application/json'})"}
{"level": "DEBUG", "message": "request_id: None"}
{"level": "DEBUG", "message": "coach_content_source: content (standard path)"}
{"level": "INFO", "message": "LLM usage: agent=coach, index=2499, turn=1, prompt_tokens=4440, completion_tokens=454, total_tokens=4894"}
{"level": "INFO", "message": "turn_complete: index=2499, turn=1, decision=accept, score=5"}
{"level": "DEBUG", "message": "example_extracted: index=2499, turn=1, input_len=4577, output_len=2900"}
{"level": "INFO", "message": "target_accepted: index=2499, coach_turns=1, total_invocations=1, score=5"}
{"level": "INFO", "message": "target_tokens: index=2499, prompt_tokens=8984, completion_tokens=1534, total_tokens=10518"}
{"level": "DEBUG", "message": "Checkpoint saved: target_index=2499"}
{"level": "INFO", "message": "complete: accepted=954, rejected=140, total_turns=2374, elapsed_seconds=83414.1"}
{"level": "INFO", "message": "pipeline_tokens: prompt_tokens=18075800, completion_tokens=3061774, total_tokens=21137574"}
{"level": "INFO", "message": "Lock released: output/.lock"}
{"level": "INFO", "message": "Pipeline complete: accepted=954, rejected=140, turns=2374, elapsed=83414.1s"}
{"level": "INFO", "message": "Done: 954 accepted, 140 rejected out of 1094 targets"}
Run complete. Press Enter to close.
