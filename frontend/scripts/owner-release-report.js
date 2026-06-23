import process from 'node:process';

import { formatOwnerFrontendReleaseReport, releaseEnvFromProcess, validateReleaseEnv } from './validate-release-env.js';

const env = releaseEnvFromProcess();
const result = validateReleaseEnv(env);

console.log(formatOwnerFrontendReleaseReport(result, env));
process.exit(result.ok ? 0 : 1);
