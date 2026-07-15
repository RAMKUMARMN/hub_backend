import { SmartHubSkill } from '../types/index.js';
import { apiSkills, avatarEndpointSkill } from './skills/api_skills.js';
import { authSkills } from './skills/auth_skills.js';

function mapSkills(skills: SmartHubSkill[]): Record<string, SmartHubSkill> {
    return skills.reduce((acc, skill) => {
        acc[skill.name] = skill;
        return acc;
    }, {} as Record<string, SmartHubSkill>);
}

export const skillRegistry: Record<string, SmartHubSkill> = {
    ...mapSkills(authSkills),
    ...mapSkills(apiSkills),
    [avatarEndpointSkill.name]: avatarEndpointSkill,
};
