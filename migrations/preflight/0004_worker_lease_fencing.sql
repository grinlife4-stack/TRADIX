-- Read-only rollout preflight for 0004_worker_lease_fencing.sql.
-- Run as a migration operator with visibility of all factory task rows.
-- Stop new task intake and keep executors quiesced through the migration.
DO $$
DECLARE
    v_running_attempts BIGINT;
    v_active_tasks BIGINT;
BEGIN
    SELECT count(*)
      INTO v_running_attempts
      FROM factory.task_attempts
     WHERE status = 'running';

    SELECT count(*)
      INTO v_active_tasks
      FROM factory.tasks
     WHERE status IN (
         'planned',
         'implementing',
         'testing',
         'review',
         'candidate',
         'deployed_test'
     );

    IF v_running_attempts > 0 OR v_active_tasks > 0 THEN
        RAISE EXCEPTION
            'worker lease fencing preflight refused: % running attempts and % active tasks; stop executors and drain or explicitly reconcile all active work before applying migration 0004',
            v_running_attempts,
            v_active_tasks;
    END IF;

    RAISE NOTICE
        'worker lease fencing preflight passed: no running attempts or active tasks';
END
$$;
