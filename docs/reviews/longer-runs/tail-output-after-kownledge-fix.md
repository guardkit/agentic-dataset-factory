B-FP8', 'max_completion_tokens': 4096, 'stream': False, 'temperature': 0.3}, 'extra_json': {'structured_outputs': {'json': {'$defs': {'Issue': {'description': 'A specific problem identified during Coach evaluation.\\n\\nEach issue maps to a named evaluation criterion from GOAL.md and\\ncarries a severity that determines whether it blocks acceptance.', 'properties': {'criterion': {'title': 'Criterion', 'type': 'string'}, 'severity': {'enum': ['blocking', 'minor'], 'title': 'Severity', 'type': 'string'}, 'description': {'title': 'Description', 'type': 'string'}, 'suggestion': {'title': 'Suggestion', 'type': 'string'}}, 'required': ['criterion', 'severity', 'description', 'suggestion'], 'title': 'Issue', 'type': 'object'}}, 'description': 'Structured evaluation returned by the Coach agent.\\n\\nThe Coach produces one ``CoachVerdict`` per training example submitted\\nby the Player. The ``is_accepted`` property encodes the composite\\nacceptance rule used to gate output writes.\\n\\nAcceptance rule (all must hold):\\n- ``decision == \"accept\"``\\n- ``score >= 3``\\n- ``layer_correct is True``\\n- ``type_correct is True``\\n- No issues with ``severity == \"blocking\"``', 'properties': {'decision': {'enum': ['accept', 'revise'], 'title': 'Decision', 'type': 'string'}, 'score': {'maximum': 5, 'minimum': 1, 'title': 'Score', 'type': 'integer'}, 'layer_correct': {'title': 'Layer Correct', 'type': 'boolean'}, 'type_correct': {'title': 'Type Correct', 'type': 'boolean'}, 'criteria_met': {'additionalProperties': {'type': 'boolean'}, 'title': 'Criteria Met', 'type': 'object'}, 'issues': {'items': {'$ref': '#/$defs/Issue'}, 'title': 'Issues', 'type': 'array'}, 'quality_assessment': {'title': 'Quality Assessment', 'type': 'string'}}, 'required': ['decision', 'score', 'layer_correct', 'type_correct', 'criteria_met', 'issues', 'quality_assessment'], 'title': 'CoachVerdict', 'type': 'object'}}}}"}
{"level": "DEBUG", "message": "Sending HTTP Request: POST http://localhost:8002/v1/chat/completions"}
{"level": "DEBUG", "message": "send_request_headers.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "send_request_headers.complete"}
{"level": "DEBUG", "message": "send_request_body.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "send_request_body.complete"}
{"level": "DEBUG", "message": "receive_response_headers.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'date', b'Sun, 05 Apr 2026 16:55:57 GMT'), (b'server', b'uvicorn'), (b'content-length', b'8683'), (b'content-type', b'application/json')])"}
{"level": "INFO", "message": "HTTP Request: POST http://localhost:8002/v1/chat/completions \"HTTP/1.1 200 OK\""}
{"level": "DEBUG", "message": "receive_response_body.started request=<Request [b'POST']>"}
{"level": "DEBUG", "message": "receive_response_body.complete"}
{"level": "DEBUG", "message": "response_closed.started"}
{"level": "DEBUG", "message": "response_closed.complete"}
{"level": "DEBUG", "message": "HTTP Response: POST http://localhost:8002/v1/chat/completions \"200 OK\" Headers({'date': 'Sun, 05 Apr 2026 16:55:57 GMT', 'server': 'uvicorn', 'content-length': '8683', 'content-type': 'application/json'})"}
{"level": "DEBUG", "message": "request_id: None"}
{"level": "DEBUG", "message": "coach_content_source: content (standard path)"}
{"level": "INFO", "message": "LLM usage: agent=coach, index=2499, turn=1, prompt_tokens=4063, completion_tokens=1625, total_tokens=5688"}
{"level": "INFO", "message": "turn_complete: index=2499, turn=1, decision=accept, score=4"}
{"level": "DEBUG", "message": "example_extracted: index=2499, turn=1, input_len=2929, output_len=2927"}
{"level": "INFO", "message": "target_accepted: index=2499, coach_turns=1, total_invocations=1, score=4"}
{"level": "INFO", "message": "target_tokens: index=2499, prompt_tokens=8612, completion_tokens=2745, total_tokens=11357"}
{"level": "DEBUG", "message": "Checkpoint saved: target_index=2499"}
{"level": "INFO", "message": "complete: accepted=984, rejected=562, total_turns=3844, elapsed_seconds=181466.4"}
{"level": "INFO", "message": "pipeline_tokens: prompt_tokens=27360997, completion_tokens=6190904, total_tokens=33551901"}
{"level": "INFO", "message": "Lock released: output/.lock"}
{"level": "INFO", "message": "Pipeline complete: accepted=984, rejected=562, turns=3844, elapsed=181466.4s"}
{"level": "INFO", "message": "Done: 984 accepted, 562 rejected out of 1546 targets"}
Run complete. Press Enter to close.
