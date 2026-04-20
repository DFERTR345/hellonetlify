# ================================================================================
# 📌 DISCORD BOT - SERVER PROTECTION SYSTEM (서린)
# ================================================================================

import discord
from discord.ext import commands, tasks
from discord.ui import View, Select, Modal, TextInput, ChannelSelect, RoleSelect, UserSelect
import json, os, time, datetime, psutil, asyncio
from typing import Optional, Union, Literal
import random 
from captcha.image import ImageCaptcha 
import io 
import functools
import re
import traceback

# ================================================================================
# 주요 상수 및 설정
# ================================================================================

CONFIG_PATH = "guild_protect_config.json"
START_TIME = time.time()

# 사용자 활동 추적 딕셔너리들
user_actions = {}      # 테러 감지를 위한 사용자 활동 기록
punished_users = {}    # 지속적인 메시지 삭제를 위한 추적
afk_users = {}         # AFK 유저 추적
captcha_challenges = {} # 캡챠 인증 추적

# 봇 권한 설정
SPECIAL_USER_ID = (1333025294889779327, 914868227652337695, 1355698620606709902, 
                   1339604814631534667, 1295009207518498857, 1445839613934571622)
STATUS_REPORT_CHANNEL_ID = 1420337388538036284
ERROR_LOG_CHANNEL_IDS = [1457269739612274700, 1484548380532281376]

# 봇 명령어 도움말 데이터베이스
HELP_COMMANDS = {
    "general": [
        "**?av** — 프로필 사진 보기",
        "**?afk / ?잠수** — AFK 설정",
        "**?userinfo / ?유저정보** — 유저 정보 확인",
        "**?serverinfo / ?서버정보** — 서버 정보 확인",
        "**?botstatus / ?bs** — 봇 상태 정보 확인",
        "**/오토모드설정** — 오토모드 설정 보기",
        "**/인증설정** — 캡챠 인증 시스템 설정",
    ],
    "admin": [
        "**?timeout / ?타임아웃** — 유저 타임아웃",
        "**/개인정보_차단** — 개인정보 차단 기능 토글",
    ],
    "developer": [
        "**?developercheckserver / ?dcs** — 참여 서버 목록 조회",
        "**?viewconfig / ?vc** — 서버 설정 JSON 보기",
        "**?developerverify / ?dv** — 개발자 여부 체크",
        "**/developersettings** — 서버 설정 JSON 직접 수정",
    ]
}

# 기본 서버 설정
DEFAULT_CONFIG = {
    "protections": {
        "스팸 감지": False,
        "도배 방지": False,
        "링크 차단": False, 
        "관리자 권한 부여 차단": False,
        "채널 대량 생성 방지": False,
        "채널 대량 삭제 방지": False,
        "역할 대량 생성 방지": False, 
        "역할 대량 삭제 방지": False,
        "레이드 감지": False,
        "대량 멘션 감지": False,
        "@everyone/@here 방지": False,
        "개인정보 차단": False,
    },
    "punishment": {
        "types": ["DM 경고"],
        "criteria": {
            "스팸 감지": {"count": 10, "seconds": 10, "punish_types": ["DM 경고"]},
            "도배 방지": {"count": 7, "seconds": 5, "punish_types": ["DM 경고"]},
            "링크 차단": {"count": 5, "seconds": 10, "punish_types": ["DM 경고"]},
            "관리자 권한 부여 차단": {"count": 1, "seconds": 60, "punish_types": ["DM 경고"]},
            "채널 대량 생성 방지": {"count": 3, "seconds": 10, "punish_types": ["DM 경고", "타임아웃"]},
            "채널 대량 삭제 방지": {"count": 3, "seconds": 10, "punish_types": ["DM 경고", "타임아웃"]},
            "역할 대량 생성 방지": {"count": 3, "seconds": 10, "punish_types": ["DM 경고", "타임아웃"]},
            "역할 대량 삭제 방지": {"count": 3, "seconds": 10, "punish_types": ["DM 경고", "타임아웃"]},
            "레이드 감지": {"count": 5, "seconds": 10, "punish_types": ["DM 경고", "타임아웃"]},
            "대량 멘션 감지": {"count": 1, "seconds": 10, "punish_types": ["DM 경고"]},
            "@everyone/@here 방지": {"count": 1, "seconds": 10, "punish_types": ["DM 경고"]},
            "개인정보 차단": {"count": 1, "seconds": 10, "punish_types": ["DM 경고"]},
        }
    },
    "verification": { 
        "enabled": False,
        "captcha_channel": None, 
        "verified_role": None,
    },
    "log_channel": None, 
    "protect_log_channel": None, 
    "warn_log_channel": None, 
    "punishment_log_channel": None,
    "notification_channel": None,
    "warnings": {}, 
    "punishments": {},
    "whitelist": {"channels": [], "roles": [], "members": []},
    "exempt_admins": False
}

# ---------------- JSON 유틸 ----------------
def load_configs():
    """설정 파일을 로드하거나, 없으면 빈 파일을 생성합니다."""
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"경고: {CONFIG_PATH} 파일이 손상되었거나 비어있습니다.")
            return {}

def save_configs(cfgs):
    """설정 파일을 저장합니다."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfgs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"오류: {CONFIG_PATH} 파일 저장 중 문제 발생 - {e}")

configs = load_configs()

def get_config(gid: int):
    """특정 서버의 설정을 가져오고, 누락된 필드는 기본값으로 채웁니다."""
    s = str(gid)
    if s not in configs:
        configs[s] = json.loads(json.dumps(DEFAULT_CONFIG)) # Deep copy
    else:
        # 설정 병합 로직 (새 필드 추가 시 호환성 유지)
        def merge_configs(default, current):
            merged = current.copy()
            for key, default_value in default.items():
                if key not in merged:
                    merged[key] = default_value
                elif isinstance(default_value, dict) and isinstance(merged.get(key), dict):
                    merged[key] = merge_configs(default_value, merged[key])
            return merged
        configs[s] = merge_configs(DEFAULT_CONFIG, configs[s])
        
        # 하위 호환성 (Migration logic)
        if "punishment" in configs.get(s, {}):
              if "type" in configs[s]["punishment"] and "types" not in configs[s]["punishment"]:
                old_types = configs[s]["punishment"]["type"]
                configs[s]["punishment"]["types"] = [old_types] if isinstance(old_types, str) else old_types
                if "type" in configs[s]["punishment"]: del configs[s]["punishment"]["type"]
    
    if "punishment" in configs.get(s, {}) and not isinstance(configs[s]["punishment"].get("types"), list):
        configs[s]["punishment"]["types"] = ["DM 경고"]

    # criteria에 punish_types 추가 (호환성)
    if "punishment" in configs.get(s, {}) and "criteria" in configs[s]["punishment"]:
        default_criteria = DEFAULT_CONFIG["punishment"]["criteria"]
        for key, value in default_criteria.items():
            if key in configs[s]["punishment"]["criteria"]:
                if "punish_types" not in configs[s]["punishment"]["criteria"][key]:
                    configs[s]["punishment"]["criteria"][key]["punish_types"] = value.get("punish_types", ["DM 경고"])
            else:
                configs[s]["punishment"]["criteria"][key] = value

    save_configs(configs)
    return configs[s]

def check_admin_or_special(inter: discord.Interaction):
    """유저가 서버 관리자이거나 특별 유저, 또는 신뢰 멤버인지 확인합니다."""
    if inter.user.id in SPECIAL_USER_ID: return True
    if not isinstance(inter.user, discord.Member): return False
    if inter.user.guild_permissions.administrator: return True
    if inter.user.id == inter.guild.owner_id: return True
    cfg = get_config(inter.guild.id)
    if inter.user.id in cfg.get("trusted_members", []): return True
    return False

async def safe_interaction_send(inter: discord.Interaction, *args, **kwargs):
    """Interaction에서 response가 없으면 response.send_message, 이미 보냈으면 followup.send."""
    try:
        if not inter.response.is_done():
            await inter.response.send_message(*args, **kwargs)
        else:
            await inter.followup.send(*args, **kwargs)
    except discord.NotFound:
        # 인터랙션이 만료되었거나 webhook이 사라진 경우 로그만 기록
        print(f"[경고] interaction send failed: Unknown Webhook / NotFound: {inter}")
    except Exception as e:
        print(f"[에러] safe_interaction_send 실패: {e}")

def is_trusted_or_owner(inter: discord.Interaction):
    """유저가 서버장이거나 신뢰 멤버인지 확인합니다."""
    if inter.user.id in SPECIAL_USER_ID: return True
    if not isinstance(inter.user, discord.Member): return False
    if inter.user.id == inter.guild.owner_id: return True
    cfg = get_config(inter.guild.id)
    if inter.user.id in cfg.get("trusted_members", []): return True
    return False

def is_whitelisted(guild: discord.Guild, member: discord.Member, channel: Optional[discord.abc.GuildChannel] = None):
    """멤버, 역할, 채널이 화이트리스트에 포함되어 있는지 확인합니다."""
    if member.bot: return True
    
    cfg = get_config(guild.id)
    whitelist = cfg.get("whitelist", {"channels": [], "roles": [], "members": []})
    
    if member.id in SPECIAL_USER_ID: return True
    if member.id == guild.owner_id: return True
    if member.id in whitelist.get("members", []): return True
    
    try:
        member_role_ids = [role.id for role in member.roles]
        if any(role_id in member_role_ids for role_id in whitelist.get("roles", [])): return True
    except AttributeError: 
        pass
            
    if channel and channel.id in whitelist.get("channels", []): return True

    if cfg.get("exempt_admins", False) and isinstance(member, discord.Member) and member.guild_permissions.administrator: return True
    return False

# ---------------- 봇 초기화 ----------------
intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)

# ---------------- 유틸리티 로깅 ----------------
async def send_log(guild: discord.Guild, title: str, description: str, color=0x3498db, protect_log=False, log_type="general"):
    """로그 메시지를 전송합니다."""
    cfg = get_config(guild.id)
    channel_id = None
    
    if protect_log or log_type == "protect": channel_id = cfg.get("protect_log_channel")
    elif log_type == "warn": channel_id = cfg.get("warn_log_channel")
    elif log_type == "message": channel_id = cfg.get("message_log_channel") or cfg.get("log_channel")
    elif log_type == "user": channel_id = cfg.get("user_log_channel") or cfg.get("log_channel")
    elif log_type == "server": channel_id = cfg.get("server_log_channel") or cfg.get("log_channel")
    elif log_type == "watched": channel_id = cfg.get("watched_log_channel")
    else: channel_id = cfg.get("log_channel")
    
    if not channel_id: return

    channel = guild.get_channel(channel_id)
    if channel and isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links:
        embed = discord.Embed(
            title=title, 
            description=description, 
            color=color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        try: await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException, Exception): pass 

async def log_setting_change(inter: discord.Interaction, title: str, description: str):
    """설정 변경 로그를 전송합니다."""
    user = inter.user
    full_description = f"**실행 유저:** {user.mention} (`{user.id}`)\n"
    full_description += description
    await send_log(inter.guild, f"[설정 변경] {title}", full_description, color=0x2ecc71, protect_log=True)

async def send_error_log(
    title: str, 
    description: str, 
    exception: Optional[Exception] = None,
    interaction: Optional[discord.Interaction] = None,
    error_type: Optional[str] = None
):
    """시스템 오류를 지정된 오류 로그 채널로 전송합니다."""
    for channel_id in ERROR_LOG_CHANNEL_IDS:
        try:
            channel = bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                # 에러 타입 결정
                if error_type is None and exception:
                    error_type = type(exception).__name__
                elif error_type is None:
                    error_type = "Unknown Error"
                
                # Embed 생성
                embed = discord.Embed(
                    title=f"시스템 오류 | {title}",
                    color=0xff0000,
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                
                # 위치 정보 추가
                if interaction:
                    location_text = f"Interaction Type: {interaction.type.name}\n"
                    if interaction.guild:
                        location_text += f"서버: {interaction.guild.name} ({interaction.guild.id})\n"
                    if interaction.channel:
                        location_text += f"채널: {interaction.channel.name} ({interaction.channel.id})\n"
                    if interaction.user:
                        location_text += f"유저: {interaction.user.name} ({interaction.user.id})"
                    embed.add_field(name="위치", value=location_text, inline=False)
                
                # 에러 타입 추가
                embed.add_field(name="에러 타입", value=error_type, inline=False)
                
                # 에러 메시지 추가
                if exception:
                    error_msg = str(exception)[:300]
                    embed.add_field(name="에러 메시지", value=f"```{error_msg}```", inline=False)
                else:
                    embed.add_field(name="설명", value=description, inline=False)
                
                # Traceback 추가
                if exception:
                    tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
                    tb_text = ''.join(tb_lines)[:500]  # 최대 500자
                    embed.add_field(name="Traceback", value=f"```{tb_text}```", inline=False)
                
                await channel.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] 오류 로그 전송 실패 (채널 {channel_id}): {e}")

# ---------------- 봇 이벤트 및 Task ----------------
@tasks.loop(minutes=10)
async def update_status():
    """봇 상태 메시지를 업데이트합니다."""
    total_guilds = len(bot.guilds)
    total_members = sum((g.member_count or 0) for g in bot.guilds if hasattr(g, 'member_count') and g.member_count)
    activity = discord.Streaming(
        name=f"{total_guilds}개의 서버에서 {total_members}명을 지키는 중!",
        url="https://www.twitch.tv/" 
    )
    await bot.change_presence(status=discord.Status.dnd, activity=activity)

@tasks.loop(minutes=10)
async def bot_status_task():
    """시스템 상태 모니터링 로그를 전송합니다."""
    target_channel = bot.get_channel(STATUS_REPORT_CHANNEL_ID)
    if not target_channel or not isinstance(target_channel, discord.TextChannel):
        return

    try:
        uptime_seconds = time.time() - START_TIME
        uptime_str = str(datetime.timedelta(seconds=int(uptime_seconds)))
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        mem_used_gb = mem.used / (1024**3)
        mem_total_gb = mem.total / (1024**3)
        mem_percent = mem.percent
        ping = round(bot.latency * 1000)
        
        embed = discord.Embed(
            title="서린 시스템 상태",
            description="봇의 현재 성능 및 시스템 자원 사용 현황입니다.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="연결 상태", value="온라인", inline=True)
        embed.add_field(name="핑", value=f"{ping} ms", inline=True)
        embed.add_field(name="업타임", value=f"{uptime_str}", inline=False)
        embed.add_field(name="CPU 사용량", value=f"{cpu_percent:.2f}%", inline=True)
        embed.add_field(name="RAM 사용량", 
                         value=f"{mem_percent:.1f}% ({mem_used_gb:.2f} GB / {mem_total_gb:.2f} GB)", 
                         inline=True)
        embed.set_footer(text=f"서버 수: {len(bot.guilds)}개")
        
        if target_channel.permissions_for(target_channel.guild.me).send_messages:
            await target_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"봇 상태 로그 전송 권한이 없습니다. 채널 ID: {STATUS_REPORT_CHANNEL_ID}")
    except discord.HTTPException as e:
        print(f"봇 상태 전송 중 HTTP 오류: {e}")
    except Exception as e:
        print(f"봇 상태 전송 작업 중 예상치 못한 오류 발생: {type(e).__name__}: {e}")

async def check_permissions():
    """봇이 켜지거나 서버에 들어갈 때 필수 권한을 확인합니다. (콘솔 로그 전용)"""
    print("--- 봇 권한 자가 점검 ---")
    required_perms = {
        "view_audit_log": "감사 로그 보기", "manage_roles": "역할 관리",
        "kick_members": "멤버 추방", "ban_members": "멤버 차단",
        "send_messages": "메시지 보내기", "manage_messages": "메시지 관리",
        "manage_nicknames": "닉네임 관리", "embed_links": "링크 첨부", 
        "moderate_members": "멤버 제재 (타임아웃)", "manage_guild": "서버 관리 (오토모드)" 
    }
    all_guilds_checked = True
    for guild in bot.guilds:
        if not guild.chunked:
            try: await guild.chunk(cache=True)
            except (discord.ClientException, discord.Forbidden): all_guilds_checked = False; continue
        if not guild.me: all_guilds_checked = False; continue

        me = guild.me
        missing_perms = [desc for perm, desc in required_perms.items() if not getattr(me.guild_permissions, perm, False)]

        if missing_perms:
            all_guilds_checked = False
            print(f"🚫 [권한 부족] 서버 '{guild.name}' ({guild.id})에 다음 필수 권한이 없습니다: {', '.join(missing_perms)}")

    if all_guilds_checked:
        print("<a:check:1487718457662378064> 모든 서버 권한 확인 완료.")
    else:
        print("<:Notice:1487713615837532211> 일부 서버의 권한 확인 중 문제가 발생했습니다.")
    print("--- 점검 완료 ---")

# ---------------- UI Helper Functions (설정 UI 전송) ----------------
async def send_protection_ui(inter: discord.Interaction, gid: int, edit=False):
    cfg = get_config(gid)
    embed = discord.Embed(title="테러방지 기능 ON/OFF", description="드롭다운 메뉴에서 항목을 선택하여 켜거나 끄세요.", color=0x2ecc71)
    status_text = "\n".join([f"{'[켜짐]' if v else '[꺼짐]'} {k}" for k, v in cfg["protections"].items()])
    embed.add_field(name="현재 상태", value=status_text, inline=False)
    view = ProtectionView(gid, inter.user.id)
    if edit: await inter.response.edit_message(embed=embed, view=view)
    else: await inter.response.send_message(embed=embed, view=view, ephemeral=True)

async def send_punish_ui(inter: discord.Interaction, gid: int, edit=False):
    cfg = get_config(gid)
    embed = discord.Embed(title="테러방지 처벌 설정", description="설정할 항목을 선택하면, 해당 항목의 **처벌 방식**을 변경할 수 있습니다.", color=0x9b59b6)
    punish_list = []
    criteria_data = cfg.get("punishment", {}).get("criteria", {})
    if isinstance(criteria_data, dict):
        for name, values in criteria_data.items():
            if isinstance(values, dict):
                punish_types = values.get("punish_types", [])
                punish_list.append(f"**{name}**: `{', '.join(punish_types) if punish_types else '설정 안됨'}`")
    if punish_list: embed.add_field(name="현재 처벌 방식", value="\n".join(punish_list), inline=False)
    view = PunishSelectView(gid, inter.user.id)
    if edit: await inter.response.edit_message(embed=embed, view=view)
    else: await inter.response.send_message(embed=embed, view=view, ephemeral=True)

async def send_criteria_ui(inter: discord.Interaction, gid: int, edit=False):
    cfg = get_config(gid)
    embed = discord.Embed(title="테러방지 기준 설정", description="설정할 항목을 선택하면, 해당 항목의 `횟수`와 `시간`을 변경할 수 있습니다.", color=0xe67e22)
    criteria_list = []
    criteria_data = cfg.get("punishment", {}).get("criteria", {})
    if isinstance(criteria_data, dict):
        for name, values in criteria_data.items():
            if isinstance(values, dict):
                criteria_list.append(f"**{name}**: `{values.get('seconds', '?')}초` 내 `{values.get('count', '?')}회`")
    if criteria_list: embed.add_field(name="현재 기준", value="\n".join(criteria_list), inline=False)
    view = CriteriaSelectView(gid, inter.user.id)
    if edit: await inter.response.edit_message(embed=embed, view=view)
    else: await inter.response.send_message(embed=embed, view=view, ephemeral=True)

async def send_whitelist_ui(inter: discord.Interaction, gid: int, edit=False):
    cfg = get_config(gid)
    embed = discord.Embed(title="화이트리스트 설정", description="보호 기능에서 제외할 채널, 역할, 멤버를 관리합니다.", color=0xf1c40f)
    channels = [f"<#{cid}>" for cid in cfg.get('whitelist', {}).get('channels', [])]
    roles = [f"<@&{rid}>" for rid in cfg.get('whitelist', {}).get('roles', [])]
    members = [f"<@{mid}>" for mid in cfg.get('whitelist', {}).get('members', [])]
    embed.add_field(name="허용된 채널", value=", ".join(channels) if channels else "없음", inline=False)
    embed.add_field(name="허용된 역할", value=", ".join(roles) if roles else "없음", inline=False)
    embed.add_field(name="허용된 멤버", value=", ".join(members) if members else "없음", inline=False)
    view = WhitelistView(gid, inter.user.id)
    if edit: await inter.response.edit_message(embed=embed, view=view)
    else: await inter.response.send_message(embed=embed, view=view, ephemeral=True)

async def send_whitelist_editor(inter: discord.Interaction, gid: int, target_type: str):
    type_map = {"channels": "채널", "roles": "역할", "members": "멤버"}
    embed = discord.Embed(title=f"화이트리스트 [{type_map.get(target_type, '알 수 없음')}] 관리",
                          description=f"아래 드롭다운에서 추가하거나 제거할 {type_map.get(target_type, '대상')}을(를) 선택하세요.",
                          color=0xf1c40f)
    await inter.response.edit_message(embed=embed, view=WhitelistEditView(gid, inter.user.id, target_type))

# ---------------- UI Views (버튼, 메뉴 등) ----------------
class BaseUserCheckView(View):
    def __init__(self, user_id: int, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if inter.user.id != self.user_id:
            await inter.response.send_message("명령어를 실행한 유저만 조작할 수 있습니다.", ephemeral=True)
            return False
        return True

class ProtectionView(BaseUserCheckView):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(user_id)
        self.guild_id = guild_id
        cfg = get_config(guild_id)
        protections_data = cfg.get("protections", {})
        options = [
            discord.SelectOption(label=name, value=name, description=f"{name} 기능을 {'끕니다' if enabled else '켭니다'}")
            for name, enabled in protections_data.items()
        ]
        protection_select = Select(placeholder="변경할 보호 항목을 선택하세요...", options=options, min_values=1, max_values=max(1, len(options)))
        protection_select.callback = self.select_callback
        self.add_item(protection_select)

    async def select_callback(self, inter: discord.Interaction):
        cfg = get_config(self.guild_id); changes = []
        for selected in inter.data['values']:
            current_state = cfg["protections"].get(selected, False)
            new_state = not current_state
            cfg["protections"][selected] = new_state
            changes.append(f"`{selected}`: {'[켜짐]' if new_state else '[꺼짐]'}")
        save_configs(configs)
        await log_setting_change(inter, "테러방지 설정 변경", "\n".join(changes))
        await send_protection_ui(inter, self.guild_id, edit=True)

class PunishView(BaseUserCheckView):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(user_id)
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="DM 경고"), discord.SelectOption(label="타임아웃"),
            discord.SelectOption(label="킥"), discord.SelectOption(label="밴")
        ]
        current_types = get_config(guild_id).get("punishment", {}).get("types", ["DM 경고"])
        for opt in options:
            if opt.label in current_types: opt.default = True
        punish_type_select = Select(placeholder="처벌 방식을 선택하세요 (다중 선택 가능)", options=options, min_values=0, max_values=len(options))
        punish_type_select.callback = self.type_callback
        self.add_item(punish_type_select)

    async def type_callback(self, inter: discord.Interaction):
        cfg = get_config(self.guild_id)
        selected_types = inter.data.get('values', [])
        cfg["punishment"]["types"] = selected_types
        save_configs(configs)
        types_str = ", ".join(selected_types) if selected_types else "설정 안됨"
        await log_setting_change(inter, "처벌 방식 변경", f"**새 처벌 방식:** `{types_str}`")
        await send_punish_ui(inter, self.guild_id, edit=True)

class PunishTypeView(BaseUserCheckView):
    def __init__(self, guild_id: int, protection_name: str, user_id: int):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.protection_name = protection_name
        options = [
            discord.SelectOption(label="DM 경고"), discord.SelectOption(label="타임아웃"),
            discord.SelectOption(label="킥"), discord.SelectOption(label="밴"), discord.SelectOption(label="관리자 역할 제거")
        ]
        cfg = get_config(guild_id)
        current_types = cfg.get("punishment", {}).get("criteria", {}).get(protection_name, {}).get("punish_types", [])
        for opt in options:
            if opt.label in current_types: opt.default = True
        punish_type_select = Select(placeholder="처벌 방식을 선택하세요 (다중 선택 가능)", options=options, min_values=0, max_values=len(options))
        punish_type_select.callback = self.type_callback
        self.add_item(punish_type_select)
        back_button = discord.ui.Button(label="[뒤로가기]", style=discord.ButtonStyle.grey)
        back_button.callback = self.go_back
        self.add_item(back_button)

    async def type_callback(self, inter: discord.Interaction):
        cfg = get_config(self.guild_id)
        selected_types = inter.data.get('values', [])
        if "punish_types" not in cfg["punishment"]["criteria"][self.protection_name]:
            cfg["punishment"]["criteria"][self.protection_name]["punish_types"] = []
        cfg["punishment"]["criteria"][self.protection_name]["punish_types"] = selected_types
        save_configs(configs)
        types_str = ", ".join(selected_types) if selected_types else "설정 안됨"
        await log_setting_change(inter, "테러방지 처벌 방식 변경", f"**항목:** `{self.protection_name}`\n**새 처벌 방식:** `{types_str}`")
        await send_punish_ui(inter, self.guild_id, edit=True)

    async def go_back(self, inter: discord.Interaction):
        await send_punish_ui(inter, self.guild_id, edit=True)

class CriteriaSelectView(BaseUserCheckView):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(user_id)
        self.guild_id = guild_id
        options = [discord.SelectOption(label=name) for name in get_config(guild_id).get("punishment", {}).get("criteria", {}).keys()]
        if not options: options.append(discord.SelectOption(label="설정 없음", value="disabled"))
        criteria_select = Select(placeholder="기준을 변경할 항목을 선택하세요...", options=options, min_values=1, max_values=1, disabled=(len(options) == 1 and options[0].value == "disabled"))
        criteria_select.callback = self.select_callback
        self.add_item(criteria_select)

    async def select_callback(self, inter: discord.Interaction):
        selected_protection = inter.data['values'][0]
        if selected_protection == "disabled":
             await inter.response.send_message("오류: 기준 설정을 변경할 수 없습니다.", ephemeral=True); return
        await inter.response.send_modal(CriteriaModal(self.guild_id, selected_protection))

class PunishSelectView(BaseUserCheckView):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(user_id)
        self.guild_id = guild_id
        options = [discord.SelectOption(label=name) for name in get_config(guild_id).get("punishment", {}).get("criteria", {}).keys()]
        if not options: options.append(discord.SelectOption(label="설정 없음", value="disabled"))
        punish_select = Select(placeholder="처벌 방식을 변경할 항목을 선택하세요...", options=options, min_values=1, max_values=1, disabled=(len(options) == 1 and options[0].value == "disabled"))
        punish_select.callback = self.select_callback
        self.add_item(punish_select)

    async def select_callback(self, inter: discord.Interaction):
        selected_protection = inter.data['values'][0]
        if selected_protection == "disabled":
             await inter.response.send_message("오류: 처벌 설정을 변경할 수 없습니다.", ephemeral=True); return
        await inter.response.edit_message(content=f"'{selected_protection}'의 처벌 방식을 선택하세요.", embed=None, view=PunishTypeView(self.guild_id, selected_protection, self.user_id))

class WhitelistView(BaseUserCheckView):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(user_id)
        self.guild_id = guild_id
    @discord.ui.button(label="채널 관리", style=discord.ButtonStyle.green)
    async def edit_channels(self, inter: discord.Interaction, button: discord.ui.Button): await send_whitelist_editor(inter, self.guild_id, 'channels')
    @discord.ui.button(label="역할 관리", style=discord.ButtonStyle.green)
    async def edit_roles(self, inter: discord.Interaction, button: discord.ui.Button): await send_whitelist_editor(inter, self.guild_id, 'roles')
    @discord.ui.button(label="멤버 관리", style=discord.ButtonStyle.green)
    async def edit_members(self, inter: discord.Interaction, button: discord.ui.Button): await send_whitelist_editor(inter, self.guild_id, 'members')

class WhitelistEditView(BaseUserCheckView):
    def __init__(self, guild_id: int, user_id: int, target_type: str):
        super().__init__(user_id)
        self.guild_id = guild_id; self.target_type = target_type
        if target_type == "channels": select_menu = ChannelSelect(placeholder="추가/제거할 채널을 선택하세요", min_values=1, max_values=25)
        elif target_type == "roles": select_menu = RoleSelect(placeholder="추가/제거할 역할을 선택하세요", min_values=1, max_values=25)
        elif target_type == "members": select_menu = UserSelect(placeholder="추가/제거할 멤버를 선택하세요", min_values=1, max_values=25)
        else: select_menu = Select(placeholder="오류", options=[discord.SelectOption(label="오류")], disabled=True)
        select_menu.callback = self.select_callback; self.add_item(select_menu)
        back_button = discord.ui.Button(label="[뒤로가기]", style=discord.ButtonStyle.grey); back_button.callback = self.go_back
        self.add_item(back_button)

    async def select_callback(self, inter: discord.Interaction):
        cfg = get_config(self.guild_id); arr = cfg["whitelist"][self.target_type]; changes = []
        selected_ids = inter.data.get('values', []); resolved_items = inter.data.get('resolved', {})
        for item_id_str in selected_ids:
            try: item_id = int(item_id_str)
            except ValueError: continue
            item_mention = f"ID: {item_id}"
            if self.target_type == "channels": item_mention = f"<#{item_id}>"
            elif self.target_type == "roles": item_mention = f"<@&{item_id}>"
            elif self.target_type == "members": item_mention = f"<@{item_id}>"
            
            if item_id in arr: arr.remove(item_id); changes.append(f"[제거] {item_mention}")
            else: arr.append(item_id); changes.append(f"[추가] {item_mention}")
        save_configs(configs)
        await log_setting_change(inter, f"화이트리스트 [{self.target_type}] 변경", "\n".join(changes))
        await send_whitelist_ui(inter, self.guild_id, edit=True)
    async def go_back(self, inter: discord.Interaction): await send_whitelist_ui(inter, self.guild_id, edit=True)

# ---------------- Modals ----------------
class CriteriaModal(Modal):
    def __init__(self, gid: int, protection_name: str):
        super().__init__(title=f"'{protection_name}' 기준 설정")
        self.gid = gid; self.protection_name = protection_name
        p = get_config(gid).get("punishment", {}).get("criteria", {}).get(protection_name, {"count": 5, "seconds": 10})
        self.count = TextInput(label="허용 횟수 (숫자)", default=str(p.get('count', 5)), required=True)
        self.seconds = TextInput(label="시간(초) (숫자)", default=str(p.get('seconds', 10)), required=True)
        self.add_item(self.count); self.add_item(self.seconds)

    async def on_submit(self, inter: discord.Interaction):
        try:
            count_val, seconds_val = int(self.count.value), int(self.seconds.value)
            if count_val < 1 or seconds_val < 1: await inter.response.send_message("<:Notice:1487713615837532211> 횟수와 시간은 1 이상의 숫자여야 합니다!", ephemeral=True); return
        except ValueError: await inter.response.send_message("<:Notice:1487713615837532211> 숫자만 입력해주세요!", ephemeral=True); return
        cfg = get_config(self.gid)
        existing = cfg["punishment"]["criteria"].get(self.protection_name, {})
        cfg["punishment"]["criteria"][self.protection_name] = {**existing, "count": count_val, "seconds": seconds_val}
        save_configs(configs)
        await log_setting_change(inter, "테러방지 기준 변경", f"**항목:** `{self.protection_name}`\n**새 기준:** `{seconds_val}초` 내 `{count_val}회`")
        await send_criteria_ui(inter, self.gid, edit=True)

class DeveloperSettingsModal(Modal):
    """(개발자 전용) JSON을 직접 수정하기 위한 모달"""
    def __init__(self, guild_id: int):
        super().__init__(title=f"서버 ID: {guild_id} 설정 (JSON)")
        self.guild_id = guild_id
        
        current_config = get_config(guild_id)
        json_str = json.dumps(current_config, indent=2, ensure_ascii=False)
        
        self.json_input = TextInput(
            label="경고: 이 설정은 JSON 형식을 따릅니다.",
            style=discord.TextStyle.paragraph,
            default=json_str,
            required=True
        )
        self.add_item(self.json_input)

    async def on_submit(self, inter: discord.Interaction):
        new_json_str = self.json_input.value
        try:
            new_cfg = json.loads(new_json_str)
            configs[str(self.guild_id)] = new_cfg
            save_configs(configs)
            await inter.response.send_message(f"<a:check:1487718457662378064> 서버 ID `{self.guild_id}`의 설정이 성공적으로 저장되었습니다.", ephemeral=True)
        except json.JSONDecodeError:
            await inter.response.send_message("❌ JSON 형식이 올바르지 않습니다. 저장이 취소되었습니다.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"❌ 저장 중 알 수 없는 오류 발생: {e}", ephemeral=True)

# ---------------- Captcha Logic ----------------
def generate_image_captcha(difficulty="보통"):
    """
    쉬움: 4자리, 보통: 6자리, 어려움: 8자리
    """
    image = ImageCaptcha(width=300, height=100)

    length_map = {"쉬움": 4, "보통": 6, "어려움": 8}
    length = length_map.get(difficulty, 6)

    characters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    code = ''.join(random.choice(characters) for _ in range(length))

    data = image.generate(code)
    img_bytes = io.BytesIO(data.read())

    return code.upper(), discord.File(img_bytes, filename="captcha.png")


# ---------------- Modal ----------------
class CaptchaModal(Modal):
    def __init__(self, user_id: int, role_id: int):
        super().__init__(title="캡챠 코드 입력")
        self.user_id = user_id
        self.role_id = role_id

        self.answer_input = TextInput(
            label="이미지의 코드를 입력하세요",
            placeholder="대소문자 구분 없음",
            required=True
        )
        self.add_item(self.answer_input)

    async def on_submit(self, inter: discord.Interaction):
        # 먼저 응답을 보내서 타임아웃 방지
        await inter.response.defer(ephemeral=True)
        
        session = captcha_challenges.get(self.user_id)

        # 세션 없음 또는 만료
        if not session or time.time() > session["expires"]:
            captcha_challenges.pop(self.user_id, None)
            await safe_interaction_send(inter, 
                "⏱️ 인증 시간이 만료되었습니다. 다시 인증을 시작해주세요.",
                ephemeral=True
            )
            return

        user_answer = self.answer_input.value.strip().upper()

        if user_answer != session["code"]:
            await safe_interaction_send(inter, 
                "❌ 코드가 일치하지 않습니다. 다시 확인해주세요.",
                ephemeral=True
            )
            return

        # 인증 성공
        role = inter.guild.get_role(self.role_id)
        if not role:
            await safe_interaction_send(inter, "❌ 인증 역할이 존재하지 않습니다.", ephemeral=True)
            return

        if role not in inter.user.roles:
            try:
                await inter.user.add_roles(role, reason="캡챠 인증 성공")
            except discord.Forbidden:
                await safe_interaction_send(inter, "❌ 봇 권한이 부족합니다.", ephemeral=True)
                return

        captcha_challenges.pop(self.user_id, None)

        await safe_interaction_send(inter, 
            f"<a:check:1487718457662378064> 인증 성공! {role.mention} 역할이 지급되었습니다.",
            ephemeral=True
        )


# ---------------- Input Button View ----------------
class CaptchaInputView(discord.ui.View):
    def __init__(self, user_id: int, role_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.role_id = role_id

    @discord.ui.button(label="코드 입력", style=discord.ButtonStyle.primary)
    async def input_btn(self, inter: discord.Interaction, _):
        if inter.user.id != self.user_id:
            await inter.response.send_message("본인만 인증할 수 있습니다.", ephemeral=True)
            return

        await inter.response.send_modal(
            CaptchaModal(self.user_id, self.role_id)
        )

    async def on_timeout(self):
        captcha_challenges.pop(self.user_id, None)


# ============================================
# 📝 수정 4: 캡챠 영구 버튼 수정 (상호작용 실패 해결)
# ============================================
# CaptchaVerifyView 클래스 전체를 아래 코드로 교체

class CaptchaVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="인증하기 (Verify)",
        style=discord.ButtonStyle.success,
        custom_id="captcha_verify_btn"
    )
    async def verify(self, inter: discord.Interaction, button: discord.ui.Button):
        cfg = get_config(inter.guild.id)
        verify_cfg = cfg.get("verification", {})

        if not verify_cfg.get("enabled", False):
            await inter.response.send_message("인증 기능이 비활성화되어 있습니다.", ephemeral=True)
            return

        role_id = verify_cfg.get("verified_role")
        role = inter.guild.get_role(role_id)

        if not role:
            await inter.response.send_message("인증 역할이 설정되지 않았습니다.", ephemeral=True)
            return

        if role in inter.user.roles:
            await inter.response.send_message("이미 인증된 상태입니다.", ephemeral=True)
            return

        difficulty = verify_cfg.get("difficulty", "보통")
        
        try:
            await inter.response.send_message("캡챠를 생성하고 있습니다...", ephemeral=True)
            
            code, file = generate_image_captcha(difficulty)
            
            captcha_challenges[inter.user.id] = {
                "code": code,
                "expires": time.time() + 180
            }

            embed = discord.Embed(
                title="보안 문자 인증",
                description=f"{len(code)}자리 코드를 확인한 후 입력해주세요.",
                color=0x3498db
            )
            embed.set_image(url="attachment://captcha.png")
            embed.set_footer(text="제한시간: 3분")

            view = CaptchaInputView(inter.user.id, role_id)

            await inter.edit_original_response(
                content=None,
                embed=embed,
                attachments=[file],
                view=view
            )
        except Exception as e:
            await inter.edit_original_response(
                content=f"캡챠 생성 중 오류가 발생했습니다: {str(e)}",
                embed=None,
                attachments=[],
                view=None
            )
# ---------------- Pagination View ----------------
class PaginationView(BaseUserCheckView):
    def __init__(self, user_id: int, embeds: list[discord.Embed], ephemeral: bool = False):
        super().__init__(user_id=user_id, timeout=120)
        self.embeds = embeds; self.current_page = 0; self.total_pages = len(embeds)
        if self.total_pages > 1:
            self.prev_button = discord.ui.Button(label="[이전]", style=discord.ButtonStyle.blurple, custom_id="prev_page")
            self.page_info = discord.ui.Button(label="1/{}".format(self.total_pages), style=discord.ButtonStyle.grey, disabled=True, custom_id="page_info")
            self.next_button = discord.ui.Button(label="[다음]", style=discord.ButtonStyle.blurple, custom_id="next_page")
            self.prev_button.callback = self.prev_page_callback
            self.next_button.callback = self.next_page_callback
            self.add_item(self.prev_button); self.add_item(self.page_info); self.add_item(self.next_button)
            self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 0)
        self.page_info.label = f"{self.current_page + 1}/{self.total_pages}"
        self.next_button.disabled = (self.current_page == self.total_pages - 1)

    async def prev_page_callback(self, inter: discord.Interaction):
        if self.current_page > 0: self.current_page -= 1; self.update_buttons()
        await inter.response.edit_message(embed=self.embeds[self.current_page], view=self)

    async def next_page_callback(self, inter: discord.Interaction):
        if self.current_page < self.total_pages - 1: self.current_page += 1; self.update_buttons()
        await inter.response.edit_message(embed=self.embeds[self.current_page], view=self)

async def apply_punishment(guild: discord.Guild, member: discord.Member, punish_types: list[str], reason: str, protection_name: str = ""):
    """지정된 처벌 유형에 따라 멤버에게 처벌을 적용합니다."""
    
    log_title = f"처벌 적용: {member.display_name}"
    log_desc = f"**대상:** {member.mention} (`{member.id}`)\n**사유:** {reason}\n**적용 처벌:** {', '.join(punish_types)}\n"
    
    # 🔧 수정 6: DM 경고 중복 전송 방지 (처벌 후 DM은 한 번만 보냄)
    if "DM 경고" in punish_types:
        punish_data = punished_users.get(guild.id, {}).get(member.id, {})
        send_dm = True
        
        # 이미 이 처벌 사이클에서 DM을 받았다면 건너뛰기
        if punish_data.get("dm_sent", False):
            send_dm = False
        
        if send_dm:
            try: 
                await member.send(f"**{guild.name}** 서버에서 **'{reason}'**(으)로 감지되어 다음 조치가 적용되었습니다: {', '.join(punish_types)}")
                # 기존 데이터 유지하면서 dm_sent 플래그만 추가
                if member.id not in punished_users.get(guild.id, {}):
                    punished_users.setdefault(guild.id, {})[member.id] = {}
                punished_users[guild.id][member.id]["dm_sent"] = True
            except discord.Forbidden: 
                log_desc += "DM 경고: 실패 (DM 차단됨)\n"
            
    for p_type in punish_types:
        try:
            if p_type == "타임아웃":
                duration = datetime.timedelta(minutes=5)
                await member.timeout(duration, reason=reason)
                log_desc += "타임아웃: 성공 (5분 적용)\n"
            elif p_type == "킥":
                await member.kick(reason=reason)
                log_desc += "킥: 성공\n"
            elif p_type == "밴":
                await member.ban(reason=reason, delete_message_seconds=60)
                log_desc += "밴: 성공\n"
            elif p_type == "관리자 역할 제거":
                admin_roles = [role for role in member.roles if role.permissions.administrator]
                if admin_roles:
                    await member.remove_roles(*admin_roles, reason=reason)
                    log_desc += f"관리자 역할 제거: 성공 ({len(admin_roles)}개 역할 제거)\n"
                else:
                    log_desc += "관리자 역할 제거: 실패 (관리자 역할 없음)\n"
        except discord.Forbidden: 
            log_desc += f"{p_type}: 실패 (봇 권한 부족)\n"
        except discord.HTTPException as e:
            log_desc += f"{p_type}: 실패 (HTTP 오류: {e})\n"
        except Exception as e: 
            log_desc += f"{p_type}: 실패 (오류: {e})\n"

    if reason.startswith(("스팸", "도배", "링크")):
        cfg = get_config(guild.id)
        delete_duration = 300
        
        if protection_name:
            criteria = cfg.get("punishment", {}).get("criteria", {}).get(protection_name, {})
            delete_duration = criteria.get("seconds", 300)
        
        # 🔧 수정 10: 새로운 처벌 시 dm_sent 플래그 초기화 (다음 처벌에서 DM을 보내도록)
        punished_users.setdefault(guild.id, {})[member.id] = {
            "timestamp": time.time(),
            "duration": delete_duration,
            "dm_sent": False  # 새로운 처벌 사이클에서 DM 플래그 초기화
        }
    await send_log(guild, log_title, log_desc, color=0xe74c3c, protect_log=True)


async def check_and_punish(member: discord.Member, protection_name: str, channel: Optional[discord.abc.GuildChannel] = None):
    """사용자 활동을 검사하여 처벌 기준을 충족했는지 확인하고, 충족 시 처벌을 적용합니다."""
    try:
        guild = member.guild; cfg = get_config(guild.id)
        
        # 화이트리스트 체크: 멤버, 역할, 채널 중 하나라도 포함되면 처벌 안함
        if is_whitelisted(guild, member, channel): return False
        if not cfg["protections"].get(protection_name, False): return False
            
        criteria = cfg["punishment"]["criteria"].get(protection_name)
        if not criteria or criteria.get("count", 0) <= 0 or criteria.get("seconds", 0) <= 0: return False
            
        count = criteria["count"]; seconds = criteria["seconds"]
        user_id = member.id; current_time = time.time()
        
        user_guild_actions = user_actions.setdefault(guild.id, {}).setdefault(user_id, {})
        actions = user_guild_actions.get(protection_name, [])
        
        recent_actions = [a for a in actions if current_time - a[0] <= seconds]
        
        user_actions[guild.id][user_id][protection_name] = recent_actions
        
        if len(recent_actions) >= count:
            # 🔧 수정 8: 처벌 타입 가져오기 수정 (null check 추가)
            punish_types = criteria.get("punish_types")
            if not punish_types:
                punish_types = cfg["punishment"].get("types", ["DM 경고"])
            if not punish_types or not isinstance(punish_types, list) or len(punish_types) == 0:
                punish_types = ["DM 경고"]
            
            reason = f"{protection_name} 정책 위반 (기준: {seconds}초 내 {count}회)"
            await apply_punishment(guild, member, punish_types, reason, protection_name)
            
            user_actions[guild.id][user_id][protection_name] = [] 
            return True
            
        return False
    except Exception as e:
        try:
            await send_error_log("check_and_punish 처벌 적용 오류", f"멤버: {member.mention} ({member.id})\n보호: {protection_name}\n서버: {member.guild.name} ({member.guild.id})", e)
        except:
            pass
        return False

# ---------------- AutoMod Views ----------------
class AutoModSettingsView(BaseUserCheckView):
    def __init__(self, user_id: int): super().__init__(user_id)
    @discord.ui.button(label="규칙 생성", style=discord.ButtonStyle.green)
    async def create_rule(self, inter, button):
        await inter.response.edit_message(content="생성할 규칙 유형을 선택하세요.", embed=None, view=AutoModCreateTypeView(self.user_id))
    @discord.ui.button(label="규칙 활성화/비활성화", style=discord.ButtonStyle.secondary)
    async def toggle_rule(self, inter, button):
        rules = await inter.guild.fetch_automod_rules()
        if not rules: return await inter.response.send_message("규칙이 없습니다.", ephemeral=True)
        await inter.response.edit_message(content="활성화/비활성화할 규칙을 선택하세요.", embed=None, view=AutoModToggleView(self.user_id, rules))
    @discord.ui.button(label="규칙 제거", style=discord.ButtonStyle.red)
    async def delete_rule(self, inter, button):
        rules = await inter.guild.fetch_automod_rules()
        if not rules: return await inter.response.send_message("규칙이 없습니다.", ephemeral=True)
        await inter.response.edit_message(content="제거할 규칙을 선택하세요.", embed=None, view=AutoModDeleteView(self.user_id, rules))

class AutoModCreateTypeView(BaseUserCheckView):
    def __init__(self, user_id: int): super().__init__(user_id)
    @discord.ui.select(placeholder="생성할 규칙 유형 선택...", options=[
        discord.SelectOption(label="키워드 차단", value="keyword"), 
        discord.SelectOption(label="멘션 스팸", value="mention_spam"),
        discord.SelectOption(label="유해 링크 차단", value="invites")
        ])
    async def select_callback(self, inter, select):
        if select.values[0] == "keyword": await inter.response.send_modal(KeywordRuleModal(inter.guild.id))
        elif select.values[0] == "mention_spam": await inter.response.send_modal(MentionRuleModal(inter.guild.id))
        elif select.values[0] == "invites": await inter.response.send_modal(LinkRuleModal(inter.guild.id))
    
    @discord.ui.button(label="[뒤로가기]", style=discord.ButtonStyle.grey)
    async def back(self, inter: discord.Interaction, button: discord.ui.Button): 
        # send_automod_settings_ui는 이 파일에 없으므로, 해당 함수를 호출하도록 가정
        await send_automod_settings_ui(inter, edit=True)

class AutoModToggleView(BaseUserCheckView):
    def __init__(self, uid: int, rules: list[discord.AutoModRule]):
        super().__init__(uid)
        self.rules = rules
        options = [discord.SelectOption(label=r.name, value=str(r.id), emoji="🟢" if r.enabled else "🔴") for r in rules[:25]]
        s = Select(options=options, placeholder="활성화/비활성화할 규칙 선택", min_values=1, max_values=1); s.callback = self.toggle_cb; self.add_item(s)
        back_button = discord.ui.Button(label="[뒤로가기]", style=discord.ButtonStyle.grey); back_button.callback = self.go_back
        self.add_item(back_button)

    async def toggle_cb(self, inter: discord.Interaction):
        rid = int(inter.data['values'][0]); rule = next((r for r in self.rules if r.id == rid), None)
        if not rule: return await inter.response.send_message("규칙을 찾을 수 없습니다.", ephemeral=True)
        await rule.edit(enabled=not rule.enabled)
        rules = await inter.guild.fetch_automod_rules() # 새로고침
        await send_automod_settings_ui(inter, edit=True)

    async def go_back(self, inter: discord.Interaction):
        await send_automod_settings_ui(inter, edit=True)

class AutoModDeleteView(BaseUserCheckView):
    def __init__(self, uid: int, rules: list[discord.AutoModRule]):
        super().__init__(uid)
        self.rules = rules
        options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in rules[:25]]
        s = Select(options=options, placeholder="제거할 규칙 선택", min_values=1, max_values=1); s.callback = self.delete_cb; self.add_item(s)
        back_button = discord.ui.Button(label="[뒤로가기]", style=discord.ButtonStyle.grey); back_button.callback = self.go_back
        self.add_item(back_button)

    async def go_back(self, inter: discord.Interaction):
        await send_automod_settings_ui(inter, edit=True)
        
    async def delete_cb(self, inter: discord.Interaction):
        rid = int(inter.data['values'][0]); rule = next((r for r in self.rules if r.id == rid), None)
        if not rule: return await inter.response.send_message("규칙을 찾을 수 없습니다.", ephemeral=True)
        await rule.delete()
        await inter.response.send_message(f"<a:check:1487718457662378064> 규칙 '{rule.name}'이(가) 제거되었습니다.", ephemeral=True)
        await send_automod_settings_ui(inter, edit=False)

class KeywordRuleModal(Modal, title="키워드 차단 규칙 생성"):
    # get_config 함수가 필요함
    def __init__(self, guild_id: int): super().__init__(); self.guild_id = guild_id
    name = TextInput(label="규칙 이름", required=True)
    keywords = TextInput(label="키워드 (쉼표 구분, 최대 100개)", style=discord.TextStyle.paragraph, required=True)
    
    async def on_submit(self, inter: discord.Interaction):
        # get_config 함수가 필요함
        cfg = get_config(self.guild_id); cid = cfg.get("protect_log_channel")
        actions = [
            discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)
        ]
        if cid: 
            actions.append(discord.AutoModRuleAction(type=discord.AutoModRuleActionType.send_alert_message, channel_id=cid))
            
        await inter.guild.create_automod_rule(
            name=self.name.value, 
            event_type=discord.AutoModRuleEventType.message_send,
            trigger_type=discord.AutoModRuleTriggerType.keyword,
            trigger_metadata=discord.AutoModTriggerMetadata(
                keyword_filter=[k.strip() for k in self.keywords.value.split(',')]
            ), 
            actions=actions
        )
        await inter.response.send_message(f"<a:check:1487718457662378064> 키워드 차단 규칙 '{self.name.value}' 생성 완료.", ephemeral=True)

class MentionRuleModal(Modal, title="멘션 스팸 규칙 생성"):
    # get_config 함수가 필요함
    def __init__(self, guild_id: int): super().__init__(); self.guild_id = guild_id
    name = TextInput(label="규칙 이름", required=True)
    limit = TextInput(label="제한 수 (멘션 최대 개수, 숫자)", required=True)
    
    async def on_submit(self, inter: discord.Interaction):
        try: l = int(self.limit.value)
        except ValueError: return await inter.response.send_message("❌ 제한 수에는 숫자만 입력해주세요.", ephemeral=True)
        if l < 1: return await inter.response.send_message("❌ 제한 수는 1 이상이어야 합니다.", ephemeral=True)

        cfg = get_config(self.guild_id); cid = cfg.get("protect_log_channel")
        actions = [
            discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message), 
            discord.AutoModRuleAction(type=discord.AutoModRuleActionType.timeout, duration=datetime.timedelta(minutes=10))
        ]
        if cid: 
            actions.append(discord.AutoModRuleAction(type=discord.AutoModRuleActionType.send_alert_message, channel_id=cid))
            
        await inter.guild.create_automod_rule(
            name=self.name.value, 
            event_type=discord.AutoModRuleEventType.message_send,
            trigger_type=discord.AutoModRuleTriggerType.mention_spam,
            trigger_metadata=discord.AutoModTriggerMetadata(
                mention_total_limit=l
            ), 
            actions=actions
        )
        await inter.response.send_message(f"<a:check:1487718457662378064> 멘션 스팸 규칙 '{self.name.value}' 생성 완료.", ephemeral=True)

class LinkRuleModal(Modal, title="유해 링크 차단 규칙 생성"):
    # get_config 함수가 필요함
    def __init__(self, guild_id: int): super().__init__(); self.guild_id = guild_id
    name = TextInput(label="규칙 이름", required=True, default="유해 링크 차단")
    
    async def on_submit(self, inter: discord.Interaction):
        cfg = get_config(self.guild_id); cid = cfg.get("protect_log_channel")
        actions = [
            discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message), 
        ]
        if cid: 
            actions.append(discord.AutoModRuleAction(type=discord.AutoModRuleActionType.send_alert_message, channel_id=cid))
            
        await inter.guild.create_automod_rule(
            name=self.name.value, 
            event_type=discord.AutoModRuleEventType.message_send,
            trigger_type=discord.AutoModRuleTriggerType.keyword_preset,
            trigger_metadata=discord.AutoModTriggerMetadata(
                presets=[discord.AutoModKeywordPresetType.invites]
            ), 
            actions=actions
        )
        await inter.response.send_message(f"유해 링크 차단 규칙 '{self.name.value}' 생성 완료. (스팸/초대 링크 차단)", ephemeral=True)

# ---------------- UI Helper Functions ----------------
async def send_automod_settings_ui(inter: discord.Interaction, edit: bool = False):
    if not inter.guild.me.guild_permissions.manage_guild: 
        if edit: return await inter.response.edit_message(content="❌ [권한 부족] '서버 관리' 권한이 필요합니다.", embed=None, view=None)
        else: return await inter.response.send_message("❌ [권한 부족] '서버 관리' 권한이 필요합니다.", ephemeral=True)
        
    rules = await inter.guild.fetch_automod_rules()
    
    description = f"**총 규칙:** {len(rules)}개\n\n"
    if rules:
        description += "**설정된 규칙:**\n"
        for i, rule in enumerate(rules[:10]): 
            status = "🟢 ON" if rule.enabled else "🔴 OFF"
            description += f"• `{rule.name}` (`{rule.id}`): {status}\n"
        if len(rules) > 10: description += f"...\n(나머지 {len(rules)-10}개 규칙은 선택 메뉴에서 확인 가능)"
    else: description += "설정된 오토모드 규칙이 없습니다."
        
    embed = discord.Embed(title="<:moderator:1487713911456141343> 오토모드 설정", description=description, color=discord.Color.blue())
    view = AutoModSettingsView(inter.user.id)
    
    if edit: await inter.response.edit_message(embed=embed, view=view, content=None)
    else: await inter.response.send_message(embed=embed, view=view, ephemeral=True)

# ---------------- Slash Commands ----------------
@bot.tree.command(name="오토모드설정", description="Discord 기본 오토모드 규칙 관리")
@discord.app_commands.checks.has_permissions(manage_guild=True)
async def automod_settings(inter: discord.Interaction):
    # check_admin_or_special 함수가 필요함
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한 없음", ephemeral=True); return
    await send_automod_settings_ui(inter, edit=False)

@bot.tree.command(name="인증설정", description="캡챠 인증 시스템을 설정합니다.")
@discord.app_commands.describe(
    channel="인증 버튼을 생성할 채널",
    verified_role="인증 성공 시 지급할 역할",
    difficulty="캡챠 난이도 (글자 수 차이)",
    enable="시스템 활성화 여부"
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def verify_setup_cmd(
    inter: discord.Interaction, 
    channel: discord.TextChannel, 
    verified_role: discord.Role, 
    difficulty: Literal['쉬움', '보통', '어려움'], 
    enable: bool
):
    if not check_admin_or_special(inter): 
        await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True)
        return
    
    # 봇의 권한 체크
    if inter.guild.me.top_role <= verified_role:
        await safe_interaction_send(inter, "❌ **설정 실패:** 봇의 역할이 지급하려는 역할보다 낮습니다. 봇 역할을 더 위로 올려주세요.", ephemeral=True)
        return

    # 설정 저장
    cfg = get_config(inter.guild.id)
    cfg["verification"]["captcha_channel"] = channel.id
    cfg["verification"]["verified_role"] = verified_role.id
    cfg["verification"]["difficulty"] = difficulty # 난이도 저장
    cfg["verification"]["enabled"] = enable
    save_configs(configs)
    
    if enable:
        # 기존 봇 메시지 정리 (깔끔하게)
        try:
            async for message in channel.history(limit=10):
                if message.author == bot.user and message.components: 
                    await message.delete()
        except: pass # 메시지 읽기/삭제 권한 없으면 패스

        # 인증 안내 임베드 생성
        embed = discord.Embed(
            title="<:moderator:1487713911456141343> 서버 입장 인증", 
            description=f"서버 활동을 시작하려면 아래 **[인증하기]** 버튼을 눌러주세요.\n인증 완료 시 {verified_role.mention} 역할이 지급됩니다.", 
            color=0x2ecc71
        )
        embed.add_field(name="인증 방법", value="1. **인증하기** 버튼 클릭\n2. 나타나는 이미지의 문자 확인\n3. **코드 입력** 버튼을 눌러 입력", inline=False)
        embed.set_footer(text=f"난이도: {difficulty}")
        
        view = CaptchaVerifyView() # 영구 View
        try:
            await channel.send(embed=embed, view=view)
            await safe_interaction_send(inter, f"<a:check:1487718457662378064> 설정 완료!\n대상 채널: {channel.mention}\n지급 역할: {verified_role.mention}\n난이도: {difficulty}\n상태: ON", ephemeral=True)
            
            # 로그 기록
            await log_setting_change(inter, "인증 시스템 설정", f"**채널:** {channel.mention}\n**역할:** {verified_role.mention}\n**난이도:** {difficulty}\n**상태:** [켜짐]")
        except discord.Forbidden:
            await safe_interaction_send(inter, f"❌ **권한 부족:** {channel.mention} 채널에 메시지를 보낼 수 없습니다.", ephemeral=True)
    else:
        await safe_interaction_send(inter, "<a:check:1487718457662378064> 인증 시스템이 **[꺼짐]**으로 설정되었습니다.", ephemeral=True)
        await log_setting_change(inter, "인증 시스템 설정", f"**상태:** [꺼짐]")

@bot.tree.command(name="테러방지", description="테러방지 항목을 선택하여 ON/OFF 합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def protection_cmd(inter: discord.Interaction):
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True); return
    await send_protection_ui(inter, inter.guild.id)

@bot.tree.command(name="테러방지_처벌설정", description="테러방지에 공통으로 적용될 '처벌 방식'을 설정합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def punish_cmd(inter: discord.Interaction):
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True); return
    await send_punish_ui(inter, inter.guild.id)

@bot.tree.command(name="테러방지_기준설정", description="항목별로 '횟수/시간' 기준을 따로 설정합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def criteria_cmd(inter: discord.Interaction):
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True); return
    await send_criteria_ui(inter, inter.guild.id)

@bot.tree.command(name="관리자처벌금지", description="관리자가 테러방지 처벌을 받지 않도록 설정합니다 (ON/OFF).")
@discord.app_commands.checks.has_permissions(administrator=True)
async def admin_exempt_cmd(inter: discord.Interaction):
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True); return
    cfg = get_config(inter.guild.id)
    new_state = not cfg.get("exempt_admins", False)
    cfg["exempt_admins"] = new_state
    save_configs(configs)
    status_str = "[켜짐] (관리자 처벌 면제)" if new_state else "[꺼짐] (관리자도 처벌 받음)"
    await log_setting_change(inter, "관리자 처벌 면제 설정 변경", f"**새 설정:** {status_str}")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 관리자 처벌 면제 설정: **{status_str}**", ephemeral=True)

@bot.tree.command(name="화이트리스트", description="보호 제외 대상을 설정합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def whitelist_cmd(inter: discord.Interaction):
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True); return
    await send_whitelist_ui(inter, inter.guild.id)

@bot.tree.command(name="로그채널설정", description="일반 로그 채널을 설정합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def log_set(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter):
        return await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True)

    cfg = get_config(inter.guild.id)
    cfg["log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "로그 채널 변경", f"일반 로그 채널이 {channel.mention} (으)로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 일반 로그 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="테러방지_로그채널설정", description="테러방지 로그 채널을 설정합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def protect_log_set(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter): await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True); return
    cfg = get_config(inter.guild.id)
    cfg["protect_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "로그 채널 변경", f"테러방지 로그 채널이 {channel.mention} (으)로 설정되었습니다.")
    await safe_interaction_send(inter, f"테러방지 로그 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="개인정보_차단", description="개인정보 차단 기능을 켜거나 끕니다.")
async def personal_info_protection_cmd(inter: discord.Interaction):
    # 일반 멤버도 사용 가능하도록 수정
    pass
    cfg = get_config(inter.guild.id)
    current = cfg["protections"].get("개인정보 차단", False)
    cfg["protections"]["개인정보 차단"] = not current
    save_configs(configs)
    status = "켜짐" if not current else "꺼짐"
    await log_setting_change(inter, "개인정보 차단 설정 변경", f"**새 설정:** [{'켜짐' if not current else '꺼짐'}]")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 개인정보 차단 기능이 **{status}**으로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="핑", description="봇 상태를 확인합니다.")
async def ping_cmd(inter: discord.Interaction):
    before = time.time()
    await inter.response.defer(ephemeral=True, thinking=True)
    latency = round(bot.latency * 1000)
    after = time.time()
    process = psutil.Process(os.getpid())
    cpu, mem = psutil.cpu_percent(interval=0.5), process.memory_info().rss / 1024**2
    uptime = time.time() - START_TIME
    uptime_str = f"{int(uptime//3600)}시간 {int((uptime%3600)//60)}분"
    embed = discord.Embed(title="봇 상태", color=0x2ecc71)
    embed.add_field(name="게이트웨이 핑", value=f"{latency}ms")
    embed.add_field(name="왕복 핑", value=f"{round((after - before) * 1000)}ms")
    embed.add_field(name="CPU 사용률", value=f"{cpu:.1f}%")
    embed.add_field(name="RAM 사용량", value=f"{mem:.1f} MB")
    embed.add_field(name="업타임", value=uptime_str)
    await safe_interaction_send(inter, embed=embed)


@bot.command(name="botstatus", aliases=["bs"])
async def botstatus_cmd(ctx):
    import sys
    import platform
    latency = round(bot.latency * 1000)
    process = psutil.Process(os.getpid())
    cpu, mem = psutil.cpu_percent(interval=0.5), process.memory_info().rss / 1024**2
    uptime = time.time() - START_TIME
    uptime_str = f"{int(uptime//3600)}시간 {int((uptime%3600)//60)}분"
    
    embed = discord.Embed(title="봇 상태 정보", color=0x2ecc71)
    embed.add_field(name="Discord.py 버전", value=discord.__version__, inline=True)
    embed.add_field(name="Python 버전", value=f"{sys.version.split()[0]}", inline=True)
    embed.add_field(name="OS", value=platform.system(), inline=True)
    embed.add_field(name="게이트웨이 핑", value=f"{latency}ms", inline=True)
    embed.add_field(name="CPU 사용률", value=f"{cpu:.1f}%", inline=True)
    embed.add_field(name="RAM 사용량", value=f"{mem:.1f} MB", inline=True)
    embed.add_field(name="업타임", value=uptime_str, inline=True)
    embed.add_field(name="서버 수", value=len(bot.guilds), inline=True)
    embed.add_field(name="총 유저 수", value=sum(guild.member_count for guild in bot.guilds), inline=True)
    
    await ctx.send(embed=embed)

@bot.tree.command(name="시작하기", description="보안봇 사용법을 안내합니다.")
async def start_here_cmd(inter: discord.Interaction):
    embed = discord.Embed(title="서린 시작하기", description="서린은 서버 보호 및 테러방지를 위한 봇입니다.", color=0x3498db)
    embed.add_field(name="1. 인증 시스템 설정", value="`/인증설정` 명령어로 신규 멤버 인증을 위한 캡챠 시스템을 설정하세요.", inline=False)
    embed.add_field(name="2. 테러방지 설정", value="`/테러방지` 및 관련 명령어로 보호 기능을 설정하세요.", inline=False)
    embed.add_field(name="3. 로그 채널 설정", value="`/로그채널설정`으로 봇의 활동 로그를 받을 채널을 지정하세요.", inline=False)
    await safe_interaction_send(inter, embed=embed, ephemeral=True)

@bot.tree.command(name="경고로그", description="경고 로그가 전송될 채널을 설정합니다.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def warn_log_set(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members: 
        await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True); return
    cfg = get_config(inter.guild.id)
    cfg["warn_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "경고 로그 채널 변경", f"경고 로그 채널이 {channel.mention} (으)로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 경고 로그 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="경고", description="대상 유저에게 경고를 부여하고 로그를 남깁니다.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def warn_user(inter: discord.Interaction, member: discord.Member, amount: int = 1, *, reason: str = "사유 없음"):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members:
        return await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True)
    
    cfg = get_config(inter.guild.id)
    warn_log_channel_id = cfg.get("warn_log_channel")
    
    user_id_str = str(member.id)
    if user_id_str not in cfg["warnings"]: cfg["warnings"][user_id_str] = []

    warn_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _ in range(amount):
        cfg["warnings"][user_id_str].append({
            "moderator_id": inter.user.id,
            "reason": reason,
            "timestamp": warn_time
        })
    save_configs(configs)

    total_warnings = len(cfg["warnings"][user_id_str])
    await safe_interaction_send(inter, f"[경고] {member.mention} 님에게 경고 {amount}개가 부여되었습니다. (총 경고: {total_warnings}개)", ephemeral=False)

    if warn_log_channel_id:
        warn_channel = inter.guild.get_channel(warn_log_channel_id)
        if warn_channel and isinstance(warn_channel, discord.TextChannel) and warn_channel.permissions_for(inter.guild.me).embed_links:
            embed = discord.Embed(title="경고 부여 기록", description=f"**대상:** {member.mention}", color=0xe74c3c)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="유저 정보", value=f"**닉네임:** `{member.display_name}`\n**ID/UID:** `{member.id}`\n**총 경고 수:** `{total_warnings}개`", inline=False)
            embed.add_field(name="부여 정보", value=f"**관리자:** {inter.user.mention}\n**부여 개수:** `{amount}개`\n**사유:** `{reason}`\n**시간:** `{warn_time}`", inline=False)
            try: await warn_channel.send(embed=embed)
            except discord.Forbidden: pass

@bot.tree.command(name="경고목록", description="서버의 경고 기록을 확인합니다.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def warn_list(inter: discord.Interaction, member: Optional[discord.Member]):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members: 
        await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True); return

    await inter.response.defer(ephemeral=True, thinking=True)
    cfg = get_config(inter.guild.id)
    warnings = cfg.get("warnings", {})

    target_warnings = []
    if member:
        target_warnings = warnings.get(str(member.id), [])
        title = f"{member.display_name} 님의 경고 기록 (총 {len(target_warnings)}개)"
    else:
        for user_id, warns in warnings.items():
            if warns: target_warnings.append((user_id, warns))
        title = f"서버 전체 경고 현황 (총 {len(target_warnings)}명)"

    embeds = []
    if not target_warnings:
        embeds.append(discord.Embed(title=title, description="경고 기록이 없습니다.", color=discord.Color.light_grey()))
    elif member:
        # 특정 멤버 경고 기록 페이지네이션 (페이지당 6개 경고)
        for i in range(0, len(target_warnings), 6):
            chunk = target_warnings[i:i + 6]
            embed = discord.Embed(title=title, color=0xe74c3c)
            embed.set_thumbnail(url=member.display_avatar.url)
            description = ""
            for idx, warn in enumerate(chunk):
                moderator = inter.guild.get_member(warn['moderator_id'])
                mod_name = moderator.display_name if moderator else f"알 수 없음 ({warn['moderator_id']})"
                description += f"**{i + idx + 1}.** (관리자: {mod_name})\n  - 사유: `{warn['reason']}`\n  - 시간: `{warn['timestamp']}`\n"
            embed.description = description; embeds.append(embed)
    else:
        # 전체 유저 경고 현황 페이지네이션 (페이지당 6명)
        target_warnings.sort(key=lambda x: len(x[1]), reverse=True)
        for i in range(0, len(target_warnings), 6):
            chunk = target_warnings[i:i + 6]
            embed = discord.Embed(title=title, color=0xe74c3c)
            description = ""; current_idx = i
            for user_id_str, warns in chunk:
                user = inter.guild.get_member(int(user_id_str))
                user_name = user.display_name if user else f"탈퇴한 유저 ({user_id_str})"
                description += f"**{current_idx + 1}.** **{user_name}** 님 (총 **{len(warns)}**회)\n"
                current_idx += 1
            embed.description = description; embeds.append(embed)

    await safe_interaction_send(inter, embed=embeds[0], view=PaginationView(inter.user.id, embeds, ephemeral=True), ephemeral=True)
    
@bot.tree.command(name="help", description="서린의 도움말 확인합니다.")
async def help_slash(inter: discord.Interaction):
    user = inter.user
    member = inter.guild.get_member(user.id)
    is_admin = member and member.guild_permissions.administrator
    is_dev = user.id in SPECIAL_USER_ID

    embed = discord.Embed(
        title="서린 도움말 (/help)",
        description=f"{user.mention} 님이 사용할 수 있는 명령어 목록입니다.",
        color=0x3498db
    )

    # 일반 명령어
    embed.add_field(name="👤 일반 사용자 명령어",
                    value="\n".join(HELP_COMMANDS["general"]),
                    inline=False)

    # 관리자 명령어
    if is_admin or is_dev:
        embed.add_field(name="🔧 관리자 명령어",
                        value="\n".join(HELP_COMMANDS["admin"]),
                        inline=False)

    # 개발자 명령어
    if is_dev:
        embed.add_field(name="🛠️ 개발자 전용 명령어",
                        value="\n".join(HELP_COMMANDS["developer"]),
                        inline=False)

    embed.set_footer(text=f"{bot.user.name} | 요청자: {user}")

    await safe_interaction_send(inter, embed=embed, ephemeral=True)
    

@bot.tree.command(name="벤목록", description="서버의 차단된 유저 목록을 확인합니다.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def ban_list(inter: discord.Interaction):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.ban_members: 
        await safe_interaction_send(inter, "멤버 차단 권한이 필요합니다.", ephemeral=True); return
        
    await inter.response.defer(ephemeral=True, thinking=True)
    ban_entries = [entry async for entry in inter.guild.bans()]
    
    if not ban_entries:
        embed = discord.Embed(title="밴 목록", description="현재 서버에 밴 된 유저가 없습니다.", color=discord.Color.light_grey())
        await safe_interaction_send(inter, embed=embed, ephemeral=True); return

    embeds = []
    for i in range(0, len(ban_entries), 6):
        chunk = ban_entries[i:i + 6]
        embed = discord.Embed(title=f"밴 목록 (총 {len(ban_entries)}명)", color=0x3498db, timestamp=datetime.datetime.now(datetime.timezone.utc))
        description = ""
        for idx, entry in enumerate(chunk):
            reason_text = f"사유: `{entry.reason}`" if entry.reason else "사유: `없음`"
            description += f"**{i + idx + 1}.** **{entry.user.name}** (`{entry.user.id}`)\n  - {reason_text}\n"
        embed.description = description; embeds.append(embed)

    await safe_interaction_send(inter, embed=embeds[0], view=PaginationView(inter.user.id, embeds, ephemeral=True), ephemeral=True)

@bot.tree.command(name="developersettings", description="(개발자 전용) 서버의 설정을 JSON으로 직접 수정합니다.")
async def developer_settings_slash(inter: discord.Interaction, server_id: Optional[str] = None):
    """(개발자 전용) JSON 모달을 통해 서버 설정을 직접 수정합니다."""
    if inter.user.id not in SPECIAL_USER_ID:
        return await safe_interaction_send(inter, "봇 개발자 전용 명령어입니다.", ephemeral=True)
        
    gid_to_edit = None
    if server_id:
        try: gid_to_edit = int(server_id)
        except ValueError: await safe_interaction_send(inter, "<:Notice:1487713615837532211> 유효한 서버 ID(숫자)를 입력해야 합니다.", ephemeral=True); return
    else:
        if not inter.guild: await safe_interaction_send(inter, "<:Notice:1487713615837532211> DM에서는 서버 ID를 반드시 입력해야 합니다.", ephemeral=True); return
        gid_to_edit = inter.guild.id
        
    target_guild = bot.get_guild(gid_to_edit)
    if not target_guild:
        return await safe_interaction_send(inter, f"<:Notice:1487713615837532211> ID `{gid_to_edit}`를 가진 서버를 찾을 수 없거나 봇이 해당 서버에 없습니다.", ephemeral=True)
        
    await inter.response.send_modal(DeveloperSettingsModal(gid_to_edit))


@bot.tree.command(name="알림_보내기", description="생성된 모든 서버의 알림 채널에 알림을 보냅니다.")
@discord.app_commands.describe(
    제목="알림 제목",
    내용="알림 내용",
    색깔="임베드 색깔 (hex 코드, 예: #3498db)"
)
async def send_notification(inter: discord.Interaction, 제목: str, 내용: str, 색깔: str = "#3498db"):
    await inter.response.defer(ephemeral=True)
    
    if inter.user.id not in SPECIAL_USER_ID:
        return await safe_interaction_send(inter, "권한이 없습니다. (개발자 전용)", ephemeral=True)
    
    try:
        color = int(색깔.lstrip('#'), 16) if 색깔.startswith('#') else int(색깔, 16)
    except ValueError:
        return await safe_interaction_send(inter, "유효한 hex 색깔 코드를 입력해주세요. (예: #3498db)", ephemeral=True)
    
    embed = discord.Embed(title=제목, description=내용, color=color)
    embed.set_footer(text=f"보낸 사람: {inter.user}", icon_url=inter.user.avatar.url if inter.user.avatar else inter.user.default_avatar.url)
    
    sent_count = 0
    failed_count = 0
    for guild in bot.guilds:
        cfg = get_config(guild.id)
        channel_id = cfg.get("notification_channel")
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links:
                try:
                    await channel.send(embed=embed)
                    sent_count += 1
                except (discord.Forbidden, discord.HTTPException, Exception):
                    failed_count += 1
            else:
                failed_count += 1
        else:
            failed_count += 1
    
    await safe_interaction_send(inter, f"알림 전송 완료!\n성공: {sent_count}개 서버\n실패: {failed_count}개 서버", ephemeral=True)

# ---------------- 텍스트 기반 명령어 ----------------
@bot.command(name="av")
async def profile(ctx, user: discord.User = None):
    # 유저를 지정하지 않으면 호출한 사람 기준
    user = user or ctx.author

    embed = discord.Embed(
        title=f"{user.name}님의 프로필 사진",
        color=0x2f3136
    )
    
    # 유저의 아바타 URL
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)

    embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.avatar.url)

    await ctx.send(embed=embed)
    
@bot.command(name="afk", aliases=["잠수"])
async def afk(ctx: commands.Context, *, reason: str = "없음"):
    if not isinstance(ctx.author, discord.Member): await ctx.send("<:Notice:1487713615837532211> 이 명령어는 서버 채널에서만 사용할 수 있습니다.", delete_after=10); return
    if ctx.author.id in afk_users: await ctx.send(f"{ctx.author.mention}, 이미 잠수 상태입니다.", delete_after=5); return

    afk_users[ctx.author.id] = {"reason": reason, "start_time": time.time(), "mentions": []}
    try:
        if ctx.guild.me.top_role > ctx.author.top_role and ctx.guild.me.guild_permissions.manage_nicknames:
            await ctx.author.edit(nick=f"[AFK] {ctx.author.display_name[:25]}", reason="AFK 설정")
    except discord.Forbidden: pass
    await ctx.send(f"{ctx.author.mention}, 잠수 상태로 설정되었습니다. 이유: `{reason}`", delete_after=10)

@bot.command(name="userinfo", aliases=["유저정보"])
async def userinfo(ctx: commands.Context, *, member_input: Optional[Union[discord.Member, discord.User, int, str]] = None):
    # 1. 대상 찾기 로직
    target_user = None
    target_member = None
    
    if member_input is None:
        target_member = ctx.author
        target_user = ctx.author
    elif isinstance(member_input, (discord.Member, discord.User)):
        target_user = member_input
        if isinstance(member_input, discord.Member): target_member = member_input
        elif ctx.guild: target_member = ctx.guild.get_member(target_user.id)
    else:
        # ID나 이름으로 찾기
        try:
            if str(member_input).isdigit():
                target_user = await bot.fetch_user(int(member_input))
                if ctx.guild: target_member = ctx.guild.get_member(target_user.id)
            else:
                if ctx.guild:
                    target_member = ctx.guild.get_member_named(str(member_input))
                    if target_member: target_user = target_member.user
        except: pass
    
    if not target_user:
        await ctx.send("❌ 유저를 찾을 수 없습니다.")
        return

    # Embed 리스트 생성
    embeds = []
    
    # [Page 1] 기본 정보
    emb1 = discord.Embed(title=f"유저 정보 - {target_user.name}", color=target_member.color if target_member else discord.Color.blue())
    emb1.set_thumbnail(url=target_user.display_avatar.url)
    if target_user.banner: emb1.set_image(url=target_user.banner.url)
    
    emb1.add_field(name="기본 정보", value=f"**ID:** `{target_user.id}`\n**언급:** {target_user.mention}\n**봇 여부:** {'🤖 예' if target_user.bot else '👤 아니오'}", inline=False)
    emb1.add_field(name="계정 생성일", value=f"<t:{int(target_user.created_at.timestamp())}:F>\n(<t:{int(target_user.created_at.timestamp())}:R>)", inline=False)
    
    if target_member:
        emb1.add_field(name="서버 가입일", value=f"<t:{int(target_member.joined_at.timestamp())}:F>\n(<t:{int(target_member.joined_at.timestamp())}:R>)", inline=False)
    
    # 뱃지 확인
    flags = [f.replace('_', ' ').title() for f, v in target_user.public_flags if v]
    if flags: emb1.add_field(name="Discord 뱃지", value=", ".join(flags), inline=False)
    
    emb1.set_footer(text="페이지 1/3 - 기본 정보")
    embeds.append(emb1)

    # [Page 2] 역할 및 권한 (멤버인 경우만)
    if target_member:
        emb2 = discord.Embed(title=f"<:moderator:1487713911456141343> 역할 및 권한 - {target_user.name}", color=target_member.color)
        emb2.set_thumbnail(url=target_user.display_avatar.url)
        
        roles = [r.mention for r in target_member.roles if r.name != "@everyone"]
        roles.reverse() # 높은 역할부터 표시
        roles_str = ", ".join(roles) if roles else "없음"
        
        if len(roles_str) > 1000: roles_str = f"총 {len(roles)}개의 역할 (너무 많아서 생략됨)"
        
        emb2.add_field(name=f"보유 역할 ({len(roles)}개)", value=roles_str, inline=False)
        emb2.add_field(name="최상위 역할", value=target_member.top_role.mention, inline=True)
        emb2.add_field(name="주요 권한", value=f"관리자: {'<a:check:1487718457662378064>' if target_member.guild_permissions.administrator else '❌'}\n킥/밴: {'<a:check:1487718457662378064>' if target_member.guild_permissions.kick_members else '❌'}", inline=True)
        
        if target_member.timed_out_until:
            emb2.add_field(name="⏳ 타임아웃 상태", value=f"해제: <t:{int(target_member.timed_out_until.timestamp())}:R>", inline=False)
            
        emb2.set_footer(text="페이지 2/3 - 역할 및 권한")
        embeds.append(emb2)

    # [Page 3] 상태 및 기타
    emb3 = discord.Embed(title=f"🎮 활동 상태 - {target_user.name}", color=discord.Color.green())
    emb3.set_thumbnail(url=target_user.display_avatar.url)
    
    if target_member:
        status_map = {discord.Status.online: "🟢 온라인", discord.Status.idle: "🟡 자리비움", discord.Status.dnd: "🔴 다른 용무 중", discord.Status.offline: "⚫ 오프라인"}
        emb3.add_field(name="현재 상태", value=status_map.get(target_member.status, "알 수 없음"), inline=True)
        
        # 기기 정보 (Desktop/Mobile/Web)
        devices = []
        if target_member.desktop_status != discord.Status.offline: devices.append("💻 PC")
        if target_member.mobile_status != discord.Status.offline: devices.append("📱 모바일")
        if target_member.web_status != discord.Status.offline: devices.append("🌐 웹")
        if devices: emb3.add_field(name="접속 기기", value=", ".join(devices), inline=True)

        # 활동(Activity)
        if target_member.activities:
            activities_str = ""
            for act in target_member.activities:
                if isinstance(act, discord.Spotify):
                    activities_str += f"🎵 **Spotify**: {act.title} - {act.artist}\n"
                elif isinstance(act, discord.Game):
                    activities_str += f"🎮 **Game**: {act.name}\n"
                elif isinstance(act, discord.Streaming):
                    activities_str += f"🟣 **Stream**: [{act.name}]({act.url})\n"
                else:
                    activities_str += f"🏷️ **{act.type.name.title()}**: {act.name}\n"
            emb3.add_field(name="현재 활동", value=activities_str, inline=False)
        else:
            emb3.add_field(name="현재 활동", value="활동 없음", inline=False)
            
    emb3.set_footer(text=f"페이지 {len(embeds)}/{len(embeds)} - 상태 정보")
    embeds.append(emb3)
    
    # View 전송
    await ctx.send(embed=embeds[0], view=PaginationView(ctx.author.id, embeds))

@bot.command(name="serverinfo", aliases=["서버정보"])
async def serverinfo(ctx: commands.Context, guild_id: Optional[int] = None):
    try:
        if guild_id: guild = bot.get_guild(guild_id);
        else: guild = ctx.guild
        if not guild: await ctx.send("<:Notice:1487713615837532211> DM에서는 이 명령어를 사용할 수 없습니다."); return

        embed = discord.Embed(title=f"{guild.name} 서버 정보", color=discord.Color.blue())
        if guild.icon: embed.set_thumbnail(url=guild.icon.url);
        if guild.banner: embed.set_image(url=guild.banner.url)

        embed.add_field(name="서버 ID", value=guild.id, inline=True)
        try: owner = guild.owner or await guild.fetch_owner(); owner_mention = owner.mention
        except: owner_mention = f"ID: {guild.owner_id}"
        embed.add_field(name="서버 소유자", value=owner_mention, inline=True)
        embed.add_field(name="서버 생성일", value=f"<t:{int(guild.created_at.timestamp())}:D> (<t:{int(guild.created_at.timestamp())}:R>)", inline=True)
        
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
        text_channels = len(guild.text_channels); voice_channels = len(guild.voice_channels); category_channels = len(guild.categories); total_channels = text_channels + voice_channels + category_channels

        embed.add_field(name="멤버 수", value=f"총 {guild.member_count}명 (온라인 {online_members}명)", inline=True)
        embed.add_field(name="채널 수", value=f"총 {total_channels}개\n(텍스트: {text_channels}, 음성: {voice_channels}, 카테고리: {category_channels})", inline=True)
        embed.add_field(name="역할 수", value=f"{len(guild.roles)}개", inline=True)

        embed.add_field(name="인증 레벨", value=str(guild.verification_level).capitalize(), inline=True)
        embed.add_field(name="유해 미디어 필터", value=str(guild.explicit_content_filter).capitalize(), inline=True)
        if guild.preferred_locale: embed.add_field(name="기본 언어", value=guild.preferred_locale, inline=True)
        
        if guild.premium_tier > 0: embed.add_field(name="서버 부스트", value=f"레벨 {guild.premium_tier} ({guild.premium_subscription_count}개 부스트)", inline=True)
        else: embed.add_field(name="서버 부스트", value="레벨 0", inline=True)

        embed.add_field(name="이모지 수", value=f"{len(guild.emojis)}개", inline=True)
        
        features = [f.replace('_', ' ').title() for f in guild.features]
        if features: embed.add_field(name="서버 기능", value=", ".join(features) if len(", ".join(features)) < 1024 else f"{len(features)}개 기능", inline=False)
        
        if guild.system_channel: embed.add_field(name="시스템 메시지 채널", value=guild.system_channel.mention, inline=True)

        await ctx.send(embed=embed)
        
    except Exception as e: await ctx.send(f"🚫 정보를 가져오는 중 오류가 발생했습니다: {e}"); print(f"Serverinfo Error: {e}")

@bot.command(name="developercheckserver", aliases=["dcs"])
async def developer_check_server(ctx: commands.Context):
    """(개발자 전용) 봇이 참여 중인 모든 서버의 이름, ID, 초대장을 DM으로 전송합니다."""
    
    if ctx.author.id not in SPECIAL_USER_ID:
        try: await ctx.message.delete()
        except discord.Forbidden: pass
        return await ctx.send("봇 개발자 전용 명령어입니다.", delete_after=10)

    await ctx.message.add_reaction("⏳") 

    try:
        await ctx.author.send(f"**{bot.user.name}** 봇이 참여 중인 서버 목록 ({len(bot.guilds)}개):")
    except discord.Forbidden:
        try: await ctx.message.remove_reaction("⏳", bot.user)
        except: pass
        await ctx.message.add_reaction("❌")
        return await ctx.send("DM을 보낼 수 없습니다. 봇 개발자님, DM을 허용해주세요.", delete_after=10)

    server_list_message = ""
    for guild in bot.guilds:
        invite_link = "N/A (권한 없음)"
        try:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    invite = await channel.create_invite(max_age=3600, max_uses=1, reason="Developer Check")
                    invite_link = invite.url
                    break 
        except discord.Forbidden: invite_link = "N/A (권한 부족)"
        except Exception: invite_link = "N/A (오류)"
            
        line = f"**{guild.name}** (ID: `{guild.id}`)\n- 멤버: {guild.member_count}명\n- 초대: {invite_link}\n\n"
        
        if len(server_list_message) + len(line) > 2000:
            await ctx.author.send(server_list_message)
            server_list_message = line
        else: server_list_message += line
            
    if server_list_message:
        await ctx.author.send(server_list_message)
        
    try: await ctx.message.remove_reaction("⏳", bot.user)
    except: pass
    await ctx.message.add_reaction("<a:check:1487718457662378064>")
    
# 기존 코드의 command 함수들이 있는 위치에 추가
    
@bot.command(name="developerverify", aliases=["dv"])
async def developer_verify(ctx: commands.Context):
    """명령을 실행한 사용자가 개발자인지 확인하고 리액션으로 응답합니다."""
    if ctx.author.id in SPECIAL_USER_ID:
        await ctx.message.add_reaction("<a:check:1487718457662378064>")
    else:
        await ctx.message.add_reaction("❌")
        
@bot.command(name="help", aliases=["도움", "도움말"])
async def help_command(ctx: commands.Context):
    user = ctx.author
    is_dev = user.id in SPECIAL_USER_ID

    embed = discord.Embed(
        title="서린 도움말",
        description=f"{user.mention} 님이 사용할 수 있는 명령어 목록입니다.",
        color=0x3498db
    )

    # 일반 명령어 (이제 관리자 명령어도 일반 멤버가 사용 가능하므로 합쳐서 표시하거나 구분 유지)
    embed.add_field(name="👤 일반 사용자 명령어",
                    value="\n".join(HELP_COMMANDS["general"]),
                    inline=False)

    # 관리자 명령어 (이제 일반 멤버도 사용 가능)
    embed.add_field(name="<:moderator:1487713911456141343> 관리 및 유틸리티 명령어",
                    value="\n".join(HELP_COMMANDS["admin"]),
                    inline=False)

    # 개발자 명령어
    if is_dev:
        embed.add_field(name="🛠️ 개발자 전용 명령어",
                        value="\n".join(HELP_COMMANDS["developer"]),
                        inline=False)

    embed.set_footer(text=f"{bot.user.name} | 요청자: {user}")

    await ctx.send(embed=embed)        

@bot.command(name="timeout", aliases=["타임아웃"])
@commands.has_permissions(moderate_members=True)
async def timeout_command(ctx: commands.Context, member: discord.Member, unit: str, duration: int, *, reason: str = "사유 없음"):
    """?timeout <대상> <min/hour> <숫자> <사유>"""
    
    if unit.lower() not in ['min', 'hour']:
        await ctx.send("<:Notice:1487713615837532211> 시간 단위는 'min' (분) 또는 'hour' (시간)만 사용할 수 있습니다.", delete_after=10)
        return
        
    if duration <= 0:
        await ctx.send("<:Notice:1487713615837532211> 시간은 0보다 커야 합니다.", delete_after=10)
        return

    if not ctx.guild.me.guild_permissions.moderate_members:
        await ctx.send("❌ 봇이 '멤버 제재' 권한을 가지고 있지 않습니다.", delete_after=10)
        return
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"❌ 봇의 역할이 {member.mention} 님의 역할보다 낮거나 같아서 제재할 수 없습니다.", delete_after=10)
        return
    if member.id == ctx.author.id:
        await ctx.send("❌ 자기 자신을 제재할 수 없습니다.", delete_after=10)
        return

    if unit.lower() == 'min':
        delta = datetime.timedelta(minutes=duration)
        duration_str = f"{duration}분"
    else: # hour
        delta = datetime.timedelta(hours=duration)
        duration_str = f"{duration}시간"

    try:
        await member.timeout(delta, reason=reason)
        await ctx.send(f"<a:check:1487718457662378064> {member.mention} 님에게 {duration_str} 동안 타임아웃을 적용했습니다. (사유: {reason})")
        # 로그는 on_member_update에서 자동으로 처리됩니다.
    except Exception as e:
        await ctx.send(f"❌ 타임아웃 적용 중 오류가 발생했습니다: {e}")

@timeout_command.error
async def timeout_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ 이 명령어를 사용하려면 '멤버 제재' 권한이 필요합니다.", delete_after=10)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("<:Notice:1487713615837532211> 사용법: `?timeout <대상> <min/hour> <시간> [사유]`", delete_after=10)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("<:Notice:1487713615837532211> 해당 멤버를 찾을 수 없습니다.", delete_after=10)
    else:
        print(f"Timeout Error: {error}")


# 📝 수정 5: 봇 시작 시 영구 View 등록
# ============================================
# on_ready 이벤트의 끝 부분에 아래 코드 추가

@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user} (ID: {bot.user.id})")
    
    # 🔧 추가: 영구 View 등록 (재시작 후에도 버튼 작동)
    bot.add_view(CaptchaVerifyView())
    
    update_status.start()
    bot_status_task.start()
    try:
        await bot.tree.sync()
        print("슬래시 커맨드 동기화 완료")
    except Exception as e:
        print(f"슬래시 커맨드 동기화 실패: {e}")
    await check_permissions()

    # 봇 시작 시 각 서버의 알림 채널 확인 및 생성
    for guild in bot.guilds:
        cfg = get_config(guild.id)
        if cfg.get("notification_channel"):
            continue
        await ensure_notification_channel(guild)

# ============================================
# 통계 및 유틸리티 명령어
# ============================================

@bot.tree.command(name="서버통계", description="서버의 상세 통계를 확인합니다.")
async def server_stats(inter: discord.Interaction):
    """서버 통계를 보여줍니다."""
    guild = inter.guild
    
    # 멤버 통계
    total_members = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])
    online = len([m for m in guild.members if m.status != discord.Status.offline])
    
    # 채널 통계
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    threads = len(guild.threads)
    
    # 역할 및 이모지
    roles_count = len(guild.roles)
    emojis_count = len(guild.emojis)
    stickers_count = len(guild.stickers)
    
    # 부스트 정보
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count
    boosters = len(guild.premium_subscribers)
    
    embed = discord.Embed(
        title=f"{guild.name} 서버 통계",
        color=0x3498db,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(
        name="멤버 정보",
        value=f"**총 멤버:** {total_members}\n**유저:** {humans}\n**봇:** {bots}\n**온라인:** {online}",
        inline=True
    )
    
    embed.add_field(
        name="채널 정보",
        value=f"**텍스트:** {text_channels}\n**음성:** {voice_channels}\n**카테고리:** {categories}\n**스레드:** {threads}",
        inline=True
    )
    
    embed.add_field(
        name="기타",
        value=f"**역할:** {roles_count}\n**이모지:** {emojis_count}\n**스티커:** {stickers_count}",
        inline=True
    )
    
    embed.add_field(
        name="부스트 정보",
        value=f"**레벨:** {boost_level}\n**부스트 수:** {boost_count}\n**부스터:** {boosters}명",
        inline=True
    )
    
    embed.add_field(
        name="서버 정보",
        value=f"**생성일:** <t:{int(guild.created_at.timestamp())}:D>\n**소유자:** {guild.owner.mention}\n**인증 레벨:** {str(guild.verification_level).capitalize()}",
        inline=True
    )
    
    await safe_interaction_send(inter, embed=embed)

@bot.tree.command(name="유저통계", description="특정 유저의 통계를 확인합니다.")
async def user_stats(inter: discord.Interaction, 유저: discord.Member = None):
    """유저 통계를 보여줍니다."""
    target = 유저 or inter.user
    
    # 역할 정보
    roles = [r.mention for r in target.roles if r != inter.guild.default_role]
    roles_str = ", ".join(roles[:10]) if roles else "없음"
    if len(roles) > 10:
        roles_str += f" ...외 {len(roles) - 10}개"
    
    # 권한 정보
    key_perms = []
    if target.guild_permissions.administrator:
        key_perms.append("관리자")
    if target.guild_permissions.manage_guild:
        key_perms.append("서버 관리")
    if target.guild_permissions.manage_channels:
        key_perms.append("채널 관리")
    if target.guild_permissions.manage_roles:
        key_perms.append("역할 관리")
    if target.guild_permissions.ban_members:
        key_perms.append("멤버 차단")
    if target.guild_permissions.kick_members:
        key_perms.append("멤버 추방")
    
    perms_str = ", ".join(key_perms) if key_perms else "없음"
    
    embed = discord.Embed(
        title=f"{target.display_name}의 통계",
        color=target.color if target.color != discord.Color.default() else 0x3498db,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    
    embed.set_thumbnail(url=target.display_avatar.url)
    
    embed.add_field(
        name="기본 정보",
        value=f"**유저명:** {target}\n**ID:** `{target.id}`\n**닉네임:** {target.display_name}\n**봇:** {'예' if target.bot else '아니오'}",
        inline=False
    )
    
    embed.add_field(
        name="가입 정보",
        value=f"**계정 생성:** <t:{int(target.created_at.timestamp())}:D>\n**서버 가입:** <t:{int(target.joined_at.timestamp())}:D>",
        inline=False
    )
    
    embed.add_field(
        name=f"역할 ({len(roles)}개)",
        value=roles_str,
        inline=False
    )
    
    embed.add_field(
        name="주요 권한",
        value=perms_str,
        inline=False
    )
    
    if target.premium_since:
        embed.add_field(
            name="부스트 정보",
            value=f"부스팅 시작: <t:{int(target.premium_since.timestamp())}:D>",
            inline=False
        )
    
    if target.timed_out_until:
        embed.add_field(
            name="타임아웃",
            value=f"종료 시간: <t:{int(target.timed_out_until.timestamp())}:F>",
            inline=False
        )
    
    await safe_interaction_send(inter, embed=embed)

@bot.tree.command(name="설정백업", description="(관리자 전용) 서버 설정을 백업합니다.")
async def backup_config(inter: discord.Interaction):
    """서버 설정을 JSON 파일로 백업합니다."""
    if not check_admin_or_special(inter):
        return await safe_interaction_send(inter, "이 명령어는 서버 관리자만 사용할 수 있습니다.", ephemeral=True)
    
    cfg = get_config(inter.guild.id)
    
    backup_data = {
        "guild_id": inter.guild.id,
        "guild_name": inter.guild.name,
        "backup_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": cfg
    }
    
    filename = f"backup_{inter.guild.id}_{int(time.time())}.json"
    filepath = os.path.join(os.getcwd(), filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        await inter.response.send_message(
            f"서버 설정이 백업되었습니다.",
            file=discord.File(filepath, filename),
            ephemeral=True
        )
        
        # 백업 파일 삭제
        os.remove(filepath)
        
        await log_setting_change(inter, "설정 백업", f"{inter.user.mention}님이 서버 설정을 백업했습니다.")
    except Exception as e:
        await safe_interaction_send(inter, f"백업 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

@bot.tree.command(name="설정복원", description="(관리자 전용) 백업 파일로 서버 설정을 복원합니다.")
async def restore_config(inter: discord.Interaction, 백업파일: discord.Attachment):
    """백업 파일로 서버 설정을 복원합니다."""
    if not check_admin_or_special(inter):
        return await safe_interaction_send(inter, "이 명령어는 서버 관리자만 사용할 수 있습니다.", ephemeral=True)
    
    if not 백업파일.filename.endswith(".json"):
        return await safe_interaction_send(inter, "JSON 파일만 업로드할 수 있습니다.", ephemeral=True)
    
    await inter.response.defer(ephemeral=True)
    
    try:
        # 파일 다운로드
        backup_content = await 백업파일.read()
        backup_data = json.loads(backup_content.decode("utf-8"))
        
        if "config" not in backup_data:
            return await safe_interaction_send(inter, "유효하지 않은 백업 파일입니다.", ephemeral=True)
        
        # 설정 복원
        configs[inter.guild.id] = backup_data["config"]
        save_configs(configs)
        
        await safe_interaction_send(inter, 
            f"서버 설정이 복원되었습니다.\n"
            f"**백업 시간:** {backup_data.get('backup_time', '알 수 없음')}\n"
            f"**백업 서버:** {backup_data.get('guild_name', '알 수 없음')}",
            ephemeral=True
        )
        
        await log_setting_change(inter, "설정 복원", f"{inter.user.mention}님이 백업 파일로 서버 설정을 복원했습니다.")
    except json.JSONDecodeError:
        await safe_interaction_send(inter, "JSON 파일 파싱 중 오류가 발생했습니다.", ephemeral=True)
    except Exception as e:
        await safe_interaction_send(inter, f"복원 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

@bot.tree.command(name="청소", description="메시지를 대량 삭제합니다.")
async def purge(inter: discord.Interaction, 개수: int):
    """지정한 개수만큼 메시지를 삭제합니다."""
    if not inter.user.guild_permissions.manage_messages:
        return await safe_interaction_send(inter, "메시지 관리 권한이 필요합니다.", ephemeral=True)
    
    if 개수 < 1 or 개수 > 100:
        return await safe_interaction_send(inter, "1~100 사이의 숫자를 입력해주세요.", ephemeral=True)
    
    await inter.response.defer(ephemeral=True)
    
    try:
        deleted = await inter.channel.purge(limit=개수, before=inter.created_at)
        await safe_interaction_send(inter, f"{len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)
        
        await log_setting_change(
            inter,
            "메시지 대량 삭제",
            f"{inter.user.mention}님이 {inter.channel.mention}에서 {len(deleted)}개의 메시지를 삭제했습니다."
        )
    except discord.Forbidden:
        await safe_interaction_send(inter, "메시지 삭제 권한이 없습니다.", ephemeral=True)
    except Exception as e:
        await safe_interaction_send(inter, f"메시지 삭제 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

# ============================================
# 봇 시작 시 각 서버의 알림 채널 확인 및 생성
# ============================================

@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user} (ID: {bot.user.id})")
    
    bot.add_view(CaptchaVerifyView())
    
    update_status.start()
    bot_status_task.start()
    try:
        await bot.tree.sync()
        print("슬래시 커맨드 동기화 완료")
    except Exception as e:
        print(f"슬래시 커맨드 동기화 실패: {e}")
    await check_permissions()

    # 봇 시작 시 각 서버의 알림 채널 확인 및 생성
    for guild in bot.guilds:
        cfg = get_config(guild.id)
        if not cfg.get("notification_channel"):
            await ensure_notification_channel(guild)


async def ensure_notification_channel(guild):
    """서버에 알림 채널이 없으면 생성합니다."""
    try:
        if not guild.me.guild_permissions.manage_channels:
            print(f"서버 {guild.name}에서 채널 생성 권한이 없어 채널을 만들 수 없습니다.")
            return
        
        cfg = get_config(guild.id)
        channel_id = cfg.get("notification_channel")
        channel = None
        if channel_id:
            channel = guild.get_channel(channel_id)
        
        if not channel:
            # 채널 생성
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            # 관리자 역할에 권한 부여
            for role in guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True)
            
            channel = await guild.create_text_channel("서린-알림", overwrites=overwrites)
            cfg["notification_channel"] = channel.id
            save_configs(configs)
            print(f"서버 {guild.name}에 서린-알림 채널을 생성했습니다.")
    except Exception as e:
        print(f"서버 {guild.name}에서 채널 생성 실패: {e}")


@bot.event
async def on_guild_join(guild):
    try:
        await ensure_notification_channel(guild)
        
        owner = guild.owner
        if owner:
            embed = discord.Embed(
                title="서린을 추가해주셔서 감사합니다!",
                description="서린 봇을 서버에 추가해주셔서 감사합니다. 아래는 봇의 주요 기능 요약입니다.",
                color=0x3498db
            )
            embed.add_field(
                name="테러방지",
                value="스팸 감지, 도배 방지, 링크 차단, 관리자 권한 부여 차단, 채널 대량 생성/삭제 방지, 역할 대량 생성/삭제 방지",
                inline=False
            )
            embed.add_field(
                name="인증",
                value="캡챠 인증 시스템으로 서버 입장 시 사용자 인증",
                inline=False
            )
            embed.add_field(
                name="오토모드",
                value="디스코드 기본 오토모드 규칙 생성 및 관리 (키워드 차단, 멘션 스팸, 유해 링크 차단)",
                inline=False
            )
            embed.add_field(
                name="링크",
                value="[서은 초대링크](https://discord.com/oauth2/authorize?client_id=1460424209837850736)\n[지원 서버](https://discord.gg/ZnWmyyXF5s)\n[웹사이트](https://teamlight.pe.kr/)",
                inline=False
            )
            embed.set_footer(text="문의 사항이 있으시면 지원 서버로 오세요!")
            await owner.send(embed=embed)
    except Exception as e:
        print(f"Guild join error: {e}")


# 메시지 삭제 캐시 저장소 (메시지 ID를 추적)
message_cache = {}

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.bot or not msg.guild:
        await bot.process_commands(msg)
        return

    # 메시지 정보를 캐시에 저장 (삭제 추적용, 최대 1000개 유지)
    message_cache[msg.id] = {
        "author_id": msg.author.id,
        "author_name": str(msg.author),
        "channel_id": msg.channel.id,
        "guild_id": msg.guild.id,
        "content": msg.content,
        "timestamp": time.time()
    }
    if len(message_cache) > 1000:
        oldest_id = min(message_cache.keys(), key=lambda k: message_cache[k]["timestamp"])
        del message_cache[oldest_id]

    guild, author, content = msg.guild, msg.author, msg.content
    
    # 1. AFK 멘션 감지 및 해제
    if author.id in afk_users:
        reason = afk_users[author.id]["reason"]; del afk_users[author.id]
        try:
            if guild.me.top_role > author.top_role and guild.me.guild_permissions.manage_nicknames:
                original_name = author.display_name
                if original_name.startswith("[AFK] "):
                    await author.edit(nick=original_name[6:], reason="AFK 해제")
        except discord.Forbidden: pass
        await msg.channel.send(f"{author.mention} 님, 잠수 상태가 해제되었습니다! (**`{reason}`**)")
        await bot.process_commands(msg); return 

    mentions_list = []
    for user_id in msg.raw_mentions:
        if user_id in afk_users and user_id != author.id:
            afk_data = afk_users[user_id]; afk_member = guild.get_member(user_id)
            if afk_member and msg.id not in afk_data.get("mentions", []):
                afk_data.setdefault("mentions", []).append(msg.id) 
                mentions_list.append(f"{afk_member.mention} 님은 현재 잠수 중입니다. 이유: `{afk_data['reason']}`")
    if mentions_list: await msg.channel.send('\n'.join(mentions_list), delete_after=20)

    # 2. 화이트리스트 체크
    if is_whitelisted(guild, author, msg.channel):
        await bot.process_commands(msg)
        return

    # 🔧 수정 3: 지속적인 메시지 삭제 (설정된 초 단위 사용) + dm_sent 플래그 체크
    if author.id in punished_users.get(guild.id, {}):
        punish_data = punished_users[guild.id][author.id]
        elapsed_time = time.time() - punish_data["timestamp"]
        delete_duration = punish_data.get("duration", 300)
        
        if elapsed_time < delete_duration:
            try: 
                await msg.delete()
            except discord.Forbidden: 
                pass
            await bot.process_commands(msg)
            return
        else: 
            del punished_users[guild.id][author.id]
        
    # 경계 멤버 로깅
    cfg = get_config(guild.id)
    if author.id in cfg.get("watched_members", []):
        await send_log(guild, "[경계 멤버] 메시지 작성", f"**유저:** {author.mention}\n**채널:** {msg.channel.mention}\n**내용:** {content}", color=0xe67e22, log_type="watched")

    # 4. 테러방지 - 스팸 감지 & 링크 차단
    protection_name = "스팸 감지"
    is_link_spam = False
    
    # 🔧 수정 7: 링크 차단 처벌 적용 수정
    if any(s in content.lower() for s in ['http://', 'https://', 'www.', '.com', '.net', '.org']):
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')
        is_image = any(file.filename.lower().endswith(image_extensions) for file in msg.attachments) or any(ext in content.lower() for ext in image_extensions)
        
        if cfg["protections"].get("링크 차단", False) and not is_image:
            is_link_spam = True
            try: await msg.delete()
            except discord.Forbidden: pass
            # 링크 차단도 별도의 보호 정책이므로 분리해야 함
            link_protection_name = "링크 차단"
            user_actions.setdefault(guild.id, {}).setdefault(author.id, {}).setdefault(link_protection_name, []).append((time.time(), msg.id, content))
            if await check_and_punish(author, link_protection_name, msg.channel): await bot.process_commands(msg); return
            if is_link_spam: await bot.process_commands(msg); return
    
    # 5. 테러방지 - 스팸 감지
    if not is_link_spam: 
        user_actions.setdefault(guild.id, {}).setdefault(author.id, {}).setdefault(protection_name, []).append((time.time(), msg.id, content))
        if await check_and_punish(author, protection_name, msg.channel): await bot.process_commands(msg); return

    # 6. 테러방지 - 도배 방지
    protection_name = "도배 방지"
    current_actions = user_actions.get(guild.id, {}).get(author.id, {}).get(protection_name, [])
    
    if (time.time(), msg.id, content) not in current_actions:
         user_actions.setdefault(guild.id, {}).setdefault(author.id, {}).setdefault(protection_name, []).append((time.time(), msg.id, content))
    
    if await check_and_punish(author, protection_name, msg.channel):
         await bot.process_commands(msg); return

    # 대량 멘션 감지
    if cfg["protections"].get("대량 멘션 감지", False) and len(msg.mentions) >= 10:
        punish_types = cfg["punishment"]["criteria"].get("대량 멘션 감지", {}).get("punish_types", ["DM 경고"])
        reason = f"대량 멘션 감지 (멘션 수: {len(msg.mentions)})"
        await apply_punishment(guild, author, punish_types, reason, "대량 멘션 감지")
        try: await msg.delete()
        except: pass
        await bot.process_commands(msg); return

    # @everyone/@here 방지
    if cfg["protections"].get("@everyone/@here 방지", False) and ("@everyone" in content or "@here" in content):
        punish_types = cfg["punishment"]["criteria"].get("@everyone/@here 방지", {}).get("punish_types", ["DM 경고"])
        reason = "@everyone 또는 @here 사용 감지"
        await apply_punishment(guild, author, punish_types, reason, "@everyone/@here 방지")
        try: await msg.delete()
        except: pass
        await bot.process_commands(msg); return

    # 개인정보 차단
    if cfg["protections"].get("개인정보 차단", False):
        # IPv4 패턴
        ipv4_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
        # IPv6 패턴 (간단 버전)
        ipv6_pattern = r'\b([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        # 전화번호 패턴 (+82 또는 010-)
        phone_pattern = r'\b(\+82\s*\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4}|010[-.\s]?\d{4}[-.\s]?\d{4})\b'
        # Discord 토큰 패턴
        token_pattern = r'\b[Mm][Tt][A-Za-z0-9]{23}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{27}\b'
        
        if re.search(ipv4_pattern, content) or re.search(ipv6_pattern, content) or re.search(phone_pattern, content) or re.search(token_pattern, content):
            punish_types = cfg["punishment"]["criteria"].get("개인정보 차단", {}).get("punish_types", ["DM 경고"])
            reason = "개인정보 유출 감지 (IP, 전화번호, 토큰 등)"
            await apply_punishment(guild, author, punish_types, reason, "개인정보 차단")
            try: await msg.delete()
            except: pass
            await bot.process_commands(msg); return

@bot.event
async def on_user_update(before: discord.User, after: discord.User):
    desc = ""
    changed = False

    if before.name != after.name:
        desc += f"**이름 변경:** `{before.name}` → `{after.name}`\n"
        changed = True

    if before.avatar != after.avatar:
        desc += f"**아바타 변경됨**\n"
        changed = True

    if not changed:
        return

    for guild in bot.guilds:
        if guild.get_member(after.id):
            full_desc = f"**대상:** {after.mention} (`{after.id}`)\n{desc}"

            if before.avatar:
                full_desc += f"[이전 아바타]({before.avatar.url})\n"
            if after.avatar:
                full_desc += f"[새 아바타]({after.avatar.url})"

            await send_log(guild, "유저 프로필 수정", full_desc, 0x9b59b6)

# ------------------------------------------------
# 멤버 밴
# ------------------------------------------------
@bot.event
async def on_member_ban(guild, user):
    actor, reason = "알 수 없음", ""
    await asyncio.sleep(1.2)

    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.ban,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == user.id:
                actor = entry.user.mention
                if entry.reason:
                    reason = f"\n**사유:** {entry.reason}"
                break
    except:
        pass

    await send_log(guild, "멤버 차단", f"**대상:** {user.mention}\n**수행자:** {actor}{reason}", 0xc0392b)

# ------------------------------------------------
# 멤버 언밴
# ------------------------------------------------
@bot.event
async def on_member_unban(guild, user):
    actor = "알 수 없음"
    await asyncio.sleep(1.2)

    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.unban,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == user.id:
                actor = entry.user.mention
                break
    except:
        pass

    await send_log(guild, "멤버 차단 해제", f"**대상:** {user.mention}\n**수행자:** {actor}", 0x2ecc71)

# ------------------------------------------------
# 멤버 입장
# ------------------------------------------------
@bot.event
async def on_member_join(member):
    if member.bot:
        return
    await send_log(member.guild, "멤버 입장", f"**유저:** {member.mention}\n**계정 생성일:** <t:{int(member.created_at.timestamp())}:D>", 0x2ecc71)

    # 레이드 감지
    guild = member.guild
    cfg = get_config(guild.id)
    if cfg["protections"].get("레이드 감지", False):
        current_time = time.time()
        raid_actions = user_actions.setdefault(guild.id, {}).setdefault("raid", [])
        raid_actions.append((current_time, member.id))
        # 오래된 항목 제거
        raid_actions[:] = [a for a in raid_actions if current_time - a[0] <= 10]  # 10초 기준
        if len(raid_actions) >= 5:  # 5명
            # 처벌 적용 (마지막 멤버에게)
            punish_types = cfg["punishment"]["criteria"].get("레이드 감지", {}).get("punish_types", ["DM 경고"])
            reason = "레이드 감지 정책 위반"
            await apply_punishment(guild, member, punish_types, reason, "레이드 감지")
            user_actions[guild.id]["raid"] = []  # 리셋

# ------------------------------------------------
# 멤버 퇴장 / 킥
# ------------------------------------------------
@bot.event
async def on_member_remove(member):
    if member.bot:
        return

    actor, reason = "알 수 없음", ""
    await asyncio.sleep(1.2)

    try:
        async for entry in member.guild.audit_logs(
            action=discord.AuditLogAction.kick,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == member.id:
                actor = entry.user.mention
                if entry.reason:
                    reason = f"\n**사유:** {entry.reason}"

                await send_log(member.guild, "멤버 추방", f"**유저:** {member.mention}\n**수행자:** {actor}{reason}", 0xe67e22)
                return
    except:
        pass

    await send_log(member.guild, "멤버 퇴장", f"**유저:** {member.mention}", 0xe74c3c)

# ------------------------------------------------
# 메시지 삭제 (개선된 추적 기능)
# ------------------------------------------------
@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return

    desc = f"**작성자:** {message.author.mention} (`{message.author.id}`)\n"
    desc += f"**채널:** {message.channel.mention} (`{message.channel.id}`)\n"
    desc += f"**메시지 ID:** `{message.id}`\n"
    
    if message.created_at:
        desc += f"**작성 시각:** <t:{int(message.created_at.timestamp())}:F>\n"

    content = message.content
    if not content and message.id in message_cache:
        content = message_cache[message.id].get("content", "")
        desc += "**참고:** 캐시에서 복구된 내용입니다.\n"
        
    if content:
        desc += f"**내용:** ```{content[:1000]}```\n"

    if message.attachments:
        desc += f"**첨부파일:** {len(message.attachments)}개\n"
        for att in message.attachments[:3]:
            desc += f"  - {att.filename} ({att.size} bytes)\n"

    if message.embeds:
        desc += f"**임베드:** {len(message.embeds)}개\n"

    if message.stickers:
        desc += f"**스티커:** {len(message.stickers)}개\n"

    # 감사 로그에서 삭제자 확인 (개선된 로직)
    actor = None
    actor_detail = "본인 삭제"
    
    await asyncio.sleep(1.5)

    try:
        async for entry in message.guild.audit_logs(
            action=discord.AuditLogAction.message_delete,
            limit=10,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=8)
        ):
            if entry.target.id == message.author.id:
                if hasattr(entry.extra, "channel") and entry.extra.channel.id == message.channel.id:
                    # 메시지 삭제 시각 비교
                    time_diff = abs((datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds())
                    if time_diff < 5:
                        actor = entry.user
                        actor_detail = f"{entry.user.mention} (`{entry.user.id}`)"
                        if hasattr(entry.extra, "count"):
                            actor_detail += f" - 삭제 개수: {entry.extra.count}개"
                        break
    except discord.Forbidden:
        actor_detail = "알 수 없음 (감사 로그 권한 없음)"
    except Exception as e:
        actor_detail = f"알 수 없음 (오류: {type(e).__name__})"

    desc += f"**삭제자:** {actor_detail}\n"
    
    # 봇이 삭제한 경우 표시
    if actor and actor.id == message.guild.me.id:
        desc += "**참고:** 봇이 자동으로 삭제한 메시지입니다.\n"

    await send_log(message.guild, "메시지 삭제", desc, 0x95a5a6, log_type="message")

# ------------------------------------------------
# 메시지 대량 삭제
# ------------------------------------------------
@bot.event
async def on_raw_bulk_message_delete(payload):
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    actor = "알 수 없음"
    await asyncio.sleep(1.2)

    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.message_bulk_delete,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.extra and entry.extra.channel.id == payload.channel_id:
                actor = entry.user.mention
                break
    except:
        pass

    await send_log(
        guild,
        "메시지 대량 삭제",
        f"**채널:** <#{payload.channel_id}>\n**삭제된 메시지:** {len(payload.message_ids)}개\n**수행자:** {actor}",
        0x34495e
    )

# ------------------------------------------------
# 메시지 수정
# ------------------------------------------------
@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.author.bot:
        return

    if before.content == after.content:
        return

    # 로그 확장: 수정 시각 및 글자 수 차이 추가
    if before.author.id in get_config(before.guild.id).get("watched_members", []):
        await send_log(before.guild, "[경계 멤버] 메시지 수정", f"**유저:** {before.author.mention}\n**채널:** {before.channel.mention}\n**수정 전:** {before.content}\n**수정 후:** {after.content}", color=0xe67e22, log_type="watched")

    diff = len(after.content) - len(before.content)
    diff_str = f"({diff:+})" if diff != 0 else "(길이 변화 없음)"
    
    desc = f"**유저:** {before.author.mention} (`{before.author.id}`)\n"
    desc += f"**채널:** {before.channel.mention} ([메시지 이동]({after.jump_url}))\n"
    desc += f"**수정 시각:** <t:{int(time.time())}:F>\n\n"
    desc += f"**수정 전:**\n```{before.content[:800]}```\n"
    desc += f"**수정 후:** {diff_str}\n```{after.content[:800]}```"
    
    await send_log(before.guild, "메시지 수정", desc, 0xf39c12, log_type="message")

# ------------------------------------------------
# 멤버 업데이트 (닉네임/역할/타임아웃/부스트)
# ------------------------------------------------
@bot.event
async def on_member_update(before, after):
    guild = after.guild

    # 닉네임 변경
    if before.display_name != after.display_name:
        await send_log(
            guild,
            "닉네임 변경",
            f"**유저:** {after.mention}\n"
            f"**이전:** `{before.display_name}`\n"
            f"**이후:** `{after.display_name}`",
            0x1abc9c
        )

    # 역할 변경
    if before.roles != after.roles:
        added = [r.mention for r in after.roles if r not in before.roles]
        removed = [r.mention for r in before.roles if r not in after.roles]

        desc = f"**유저:** {after.mention}\n"
        if added:
            desc += f"**추가된 역할:** {', '.join(added)}\n"
        if removed:
            desc += f"**제거된 역할:** {', '.join(removed)}\n"

        await send_log(guild, "역할 변경", desc, 0x9b59b6, log_type="user")

    # 타임아웃
    if before.timed_out_until != after.timed_out_until:
        if after.timed_out_until is None:
            await send_log(guild, "타임아웃 해제", f"**유저:** {after.mention}", 0x2ecc71, log_type="user")
        else:
            await send_log(guild, "타임아웃 적용", f"**유저:** {after.mention}\n**종료 시간:** <t:{int(after.timed_out_until.timestamp())}:F>", 0xf1c40f, log_type="user")
    
    # 부스트 상태 변경
    if before.premium_since != after.premium_since:
        if after.premium_since and not before.premium_since:
            await send_log(
                guild,
                "서버 부스트 시작",
                f"**부스터:** {after.mention}\n**부스트 시작 시간:** <t:{int(after.premium_since.timestamp())}:F>\n**현재 부스트 레벨:** {guild.premium_tier}\n**총 부스트 수:** {guild.premium_subscription_count}",
                0xf47fff
            )
        elif not after.premium_since and before.premium_since:
            await send_log(
                guild,
                "서버 부스트 종료",
                f"**유저:** {after.mention}\n**현재 부스트 레벨:** {guild.premium_tier}\n**총 부스트 수:** {guild.premium_subscription_count}",
                0x95a5a6
            )

# ------------------------------------------------
# 보이스 상태 변경
# ------------------------------------------------
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if member.id in get_config(member.guild.id).get("watched_members", []):
        if before.channel != after.channel:
            action = "이동" if before.channel and after.channel else ("입장" if after.channel else "퇴장")
            await send_log(member.guild, f"[경계 멤버] 보이스 {action}", f"**유저:** {member.mention}\n**이전:** {before.channel.mention if before.channel else '없음'}\n**이후:** {after.channel.mention if after.channel else '없음'}", color=0xe67e22, log_type="watched")

    if before.channel is None and after.channel is not None:
        await send_log(member.guild, "보이스 입장", f"**유저:** {member.mention}\n**채널:** {after.channel.mention}", 0x2ecc71, log_type="user")

    elif before.channel is not None and after.channel is None:
        await send_log(member.guild, "보이스 퇴장", f"**유저:** {member.mention}\n**채널:** {before.channel.mention}", 0xe74c3c, log_type="user")

    elif before.channel != after.channel:
        await send_log(
            member.guild,
            "보이스 채널 이동",
            f"**유저:** {member.mention}\n"
            f"**이전:** {before.channel.mention}\n"
            f"**이동:** {after.channel.mention}",
            0xf1c40f
        )

# ------------------------------------------------
# 채널 생성 (보호 로직 추가됨)
# ------------------------------------------------
@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    actor_member = None
    
    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.channel_create,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == channel.id:
                actor_member = guild.get_member(entry.user.id)
                break
    except:
        pass

    if actor_member:
        protection_name = "채널 대량 생성 방지"
        user_actions.setdefault(guild.id, {}).setdefault(actor_member.id, {}).setdefault(protection_name, []).append((time.time(), channel.id, "create"))
        await check_and_punish(actor_member, protection_name, channel)

    # 채널 타입별 정보
    channel_type = str(channel.type).replace('_', ' ').title()
    desc = f"**채널:** {channel.mention} (`{channel.id}`)\n"
    desc += f"**유형:** {channel_type}\n"
    desc += f"**생성자:** {actor_member.mention if actor_member else '알 수 없음'}\n"
    
    if isinstance(channel, discord.TextChannel):
        desc += f"**NSFW:** {'예' if channel.is_nsfw() else '아니오'}\n"
        desc += f"**슬로우모드:** {channel.slowmode_delay}초\n"
        if channel.topic:
            desc += f"**주제:** {channel.topic[:100]}\n"
    elif isinstance(channel, discord.VoiceChannel):
        desc += f"**비트레이트:** {channel.bitrate // 1000}kbps\n"
        desc += f"**유저 제한:** {channel.user_limit if channel.user_limit else '무제한'}\n"
    
    await send_log(guild, "채널 생성", desc, 0x3498db, log_type="server")

# ------------------------------------------------
# 채널 삭제 (보호 로직 추가됨)
# ------------------------------------------------
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    actor_member = None

    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.channel_delete,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == channel.id:
                actor_member = guild.get_member(entry.user.id)
                break
    except:
        pass

    if actor_member:
        protection_name = "채널 대량 삭제 방지"
        user_actions.setdefault(guild.id, {}).setdefault(actor_member.id, {}).setdefault(protection_name, []).append((time.time(), channel.id, "delete"))
        await check_and_punish(actor_member, protection_name, None)

    await send_log(
        guild,
        "채널 삭제",
        f"**삭제된 채널:** `{channel.name}` (`{channel.id}`)\n"
        f"**수행자:** {actor_member.mention if actor_member else '알 수 없음'}",
        0xe74c3c
    )

    # notification_channel 삭제 시 설정에서 제거
    cfg = get_config(guild.id)
    if cfg.get("notification_channel") == channel.id:
        cfg["notification_channel"] = None
        save_configs(configs)

# ------------------------------------------------
# 채널 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_guild_channel_update(before, after):
    changes = []
    
    if before.name != after.name:
        changes.append(f"**이름:** `{before.name}` → `{after.name}`")
    
    if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
        if before.topic != after.topic:
            changes.append(f"**주제:** `{before.topic or '없음'}` → `{after.topic or '없음'}`")
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(f"**슬로우모드:** {before.slowmode_delay}초 → {after.slowmode_delay}초")
        if before.is_nsfw() != after.is_nsfw():
            changes.append(f"**NSFW:** {before.is_nsfw()} → {after.is_nsfw()}")
    
    if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
        if before.bitrate != after.bitrate:
            changes.append(f"**비트레이트:** {before.bitrate // 1000}kbps → {after.bitrate // 1000}kbps")
        if before.user_limit != after.user_limit:
            changes.append(f"**유저 제한:** {before.user_limit or '무제한'} → {after.user_limit or '무제한'}")
    
    if before.category != after.category:
        changes.append(f"**카테고리:** {before.category.name if before.category else '없음'} → {after.category.name if after.category else '없음'}")
    
    if before.position != after.position:
        changes.append(f"**위치:** {before.position} → {after.position}")
    
    # 권한 변경 감지
    before_overwrites = set(before.overwrites.keys())
    after_overwrites = set(after.overwrites.keys())
    
    if before_overwrites != after_overwrites:
        added = after_overwrites - before_overwrites
        removed = before_overwrites - after_overwrites
        if added:
            changes.append(f"**권한 추가:** {len(added)}개 대상")
        if removed:
            changes.append(f"**권한 제거:** {len(removed)}개 대상")
    
    if not changes:
        return
    
    details = "\n".join(changes)
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in after.guild.audit_logs(
            action=discord.AuditLogAction.channel_update,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == after.id:
                actor = entry.user.mention
                break
    except:
        pass
    
    await send_log(
        after.guild,
        "채널 수정",
        f"**채널:** {after.mention} (`{after.id}`)\n**수행자:** {actor}\n{details}",
        0xf39c12
    )

# ------------------------------------------------
# 역할 생성 (보호 로직 추가됨)
# ------------------------------------------------
@bot.event
async def on_guild_role_create(role):
    guild = role.guild
    actor_member = None

    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.role_create,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == role.id:
                actor_member = guild.get_member(entry.user.id)
                break
    except:
        pass
        
    if actor_member:
        protection_name = "역할 대량 생성 방지"
        user_actions.setdefault(guild.id, {}).setdefault(actor_member.id, {}).setdefault(protection_name, []).append((time.time(), role.id, "create"))
        await check_and_punish(actor_member, protection_name, None)

    await send_log(
        guild,
        "역할 생성",
        f"**역할:** {role.mention} (`{role.id}`)\n**생성자:** {actor_member.mention if actor_member else '알 수 없음'}",
        0x8e44ad
    )

# ------------------------------------------------
# 역할 삭제 (보호 로직 추가됨)
# ------------------------------------------------
@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    actor_member = None

    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.role_delete,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == role.id:
                actor_member = guild.get_member(entry.user.id)
                break
    except:
        pass
        
    if actor_member:
        protection_name = "역할 대량 삭제 방지"
        user_actions.setdefault(guild.id, {}).setdefault(actor_member.id, {}).setdefault(protection_name, []).append((time.time(), role.id, "delete"))
        await check_and_punish(actor_member, protection_name, None)

    await send_log(
        guild,
        "역할 삭제",
        f"**삭제된 역할:** `{role.name}` (`{role.id}`)\n**수행자:** {actor_member.mention if actor_member else '알 수 없음'}",
        0xc0392b
    )

# ------------------------------------------------
# 역할 수정
# ------------------------------------------------
@bot.event
async def on_guild_role_update(before, after):
    changes = []
    
    if before.name != after.name:
        changes.append(f"**이름:** `{before.name}` → `{after.name}`")
    if before.color != after.color:
        changes.append(f"**색상:** `{before.color}` → `{after.color}`")
    if before.hoist != after.hoist:
        changes.append(f"**역할 분리 표시:** `{before.hoist}` → `{after.hoist}`")
    if before.mentionable != after.mentionable:
        changes.append(f"**멘션 가능:** `{before.mentionable}` → `{after.mentionable}`")
    if before.position != after.position:
        changes.append(f"**위치:** `{before.position}` → `{after.position}`")
    if before.permissions != after.permissions:
        added_perms = []
        removed_perms = []
        for perm, value in before.permissions:
            if value != getattr(after.permissions, perm):
                if getattr(after.permissions, perm):
                    added_perms.append(perm)
                else:
                    removed_perms.append(perm)
        if added_perms:
            changes.append(f"**추가된 권한:** {', '.join(added_perms[:5])}")
        if removed_perms:
            changes.append(f"**제거된 권한:** {', '.join(removed_perms[:5])}")

    if not changes:
        return

    details = "\n".join(changes)
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in after.guild.audit_logs(
            action=discord.AuditLogAction.role_update,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == after.id:
                actor = entry.user.mention
                break
    except:
        pass

    await send_log(
        after.guild,
        "역할 수정",
        f"**역할:** {after.mention} (`{after.id}`)\n**수행자:** {actor}\n{details}",
        0xf39c12
    )

# ------------------------------------------------
# 서버 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_guild_update(before, after):
    changes = []
    
    if before.name != after.name:
        changes.append(f"**서버 이름:** `{before.name}` → `{after.name}`")
    if before.icon != after.icon:
        changes.append("**서버 아이콘:** 변경됨")
    if before.banner != after.banner:
        changes.append("**서버 배너:** 변경됨")
    if before.splash != after.splash:
        changes.append("**초대 배경:** 변경됨")
    if before.discovery_splash != after.discovery_splash:
        changes.append("**검색 배경:** 변경됨")
    if before.owner_id != after.owner_id:
        new_owner = after.owner or await after.fetch_owner()
        changes.append(f"**소유자 변경:** {new_owner.mention}")
    if before.afk_channel != after.afk_channel:
        changes.append(f"**AFK 채널:** {after.afk_channel.mention if after.afk_channel else '없음'}")
    if before.afk_timeout != after.afk_timeout:
        changes.append(f"**AFK 타임아웃:** {after.afk_timeout}초")
    if before.verification_level != after.verification_level:
        changes.append(f"**인증 레벨:** {str(after.verification_level).capitalize()}")
    if before.default_notifications != after.default_notifications:
        changes.append(f"**기본 알림:** {str(after.default_notifications)}")
    if before.explicit_content_filter != after.explicit_content_filter:
        changes.append(f"**유해 미디어 필터:** {str(after.explicit_content_filter)}")
    if before.mfa_level != after.mfa_level:
        changes.append(f"**2단계 인증 요구사항:** {'필요' if after.mfa_level else '불필요'}")
    if before.premium_tier != after.premium_tier:
        changes.append(f"**부스트 레벨:** {after.premium_tier}")
    if before.system_channel != after.system_channel:
        changes.append(f"**시스템 채널:** {after.system_channel.mention if after.system_channel else '없음'}")
    if before.rules_channel != after.rules_channel:
        changes.append(f"**규칙 채널:** {after.rules_channel.mention if after.rules_channel else '없음'}")
    if before.public_updates_channel != after.public_updates_channel:
        changes.append(f"**공지 채널:** {after.public_updates_channel.mention if after.public_updates_channel else '없음'}")
    
    if not changes:
        return
    
    details = "\n".join(changes)
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in after.audit_logs(
            action=discord.AuditLogAction.guild_update,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            actor = entry.user.mention
            break
    except:
        pass
    
    await send_log(
        after,
        "서버 설정 변경",
        f"**수행자:** {actor}\n{details}",
        0x3498db
    )

# ------------------------------------------------
# 초대 생성 로그
# ------------------------------------------------
@bot.event
async def on_invite_create(invite):
    desc = f"**생성자:** {invite.inviter.mention if invite.inviter else '알 수 없음'}\n"
    desc += f"**초대 코드:** `{invite.code}`\n"
    desc += f"**채널:** {invite.channel.mention if invite.channel else '알 수 없음'}\n"
    desc += f"**최대 사용 횟수:** {invite.max_uses if invite.max_uses else '무제한'}\n"
    desc += f"**만료 시간:** {invite.max_age if invite.max_age else '무제한'}초\n"
    if invite.temporary:
        desc += "**임시 멤버:** 예\n"
    
    await send_log(invite.guild, "초대 생성", desc, 0x2ecc71, log_type="server")

# ------------------------------------------------
# 초대 삭제 로그
# ------------------------------------------------
@bot.event
async def on_invite_delete(invite):
    desc = f"**초대 코드:** `{invite.code}`\n"
    desc += f"**채널:** {invite.channel.mention if invite.channel else '알 수 없음'}\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in invite.guild.audit_logs(
            action=discord.AuditLogAction.invite_delete,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.code == invite.code:
                actor = entry.user.mention
                break
    except:
        pass
    
    desc += f"**삭제자:** {actor}\n"
    
    await send_log(invite.guild, "초대 삭제", desc, 0xe74c3c, log_type="server")

# ------------------------------------------------
# 이모지 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_guild_emojis_update(guild, before, after):
    added = [e for e in after if e not in before]
    removed = [e for e in before if e not in after]
    
    if not added and not removed:
        return
    
    desc = ""
    
    if added:
        desc += "**추가된 이모지:**\n"
        for emoji in added[:10]:
            desc += f"  - {emoji} `:{emoji.name}:` (ID: `{emoji.id}`)\n"
        if len(added) > 10:
            desc += f"  ...외 {len(added) - 10}개\n"
    
    if removed:
        desc += "**삭제된 이모지:**\n"
        for emoji in removed[:10]:
            desc += f"  - `:{emoji.name}:` (ID: `{emoji.id}`)\n"
        if len(removed) > 10:
            desc += f"  ...외 {len(removed) - 10}개\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        action = discord.AuditLogAction.emoji_create if added else discord.AuditLogAction.emoji_delete
        async for entry in guild.audit_logs(
            action=action,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            actor = entry.user.mention
            break
    except:
        pass
    
    desc += f"\n**수행자:** {actor}"
    
    await send_log(guild, "이모지 변경", desc, 0xf39c12, log_type="server")

# ------------------------------------------------
# 스티커 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_guild_stickers_update(guild, before, after):
    added = [s for s in after if s not in before]
    removed = [s for s in before if s not in after]
    
    if not added and not removed:
        return
    
    desc = ""
    
    if added:
        desc += "**추가된 스티커:**\n"
        for sticker in added[:10]:
            desc += f"  - `{sticker.name}` (ID: `{sticker.id}`)\n"
        if len(added) > 10:
            desc += f"  ...외 {len(added) - 10}개\n"
    
    if removed:
        desc += "**삭제된 스티커:**\n"
        for sticker in removed[:10]:
            desc += f"  - `{sticker.name}` (ID: `{sticker.id}`)\n"
        if len(removed) > 10:
            desc += f"  ...외 {len(removed) - 10}개\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        action = discord.AuditLogAction.sticker_create if added else discord.AuditLogAction.sticker_delete
        async for entry in guild.audit_logs(
            action=action,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            actor = entry.user.mention
            break
    except:
        pass
    
    desc += f"\n**수행자:** {actor}"
    
    await send_log(guild, "스티커 변경", desc, 0x9b59b6, log_type="server")

# ------------------------------------------------
# 웹훅 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_webhooks_update(channel):
    desc = f"**채널:** {channel.mention} (`{channel.id}`)\n"
    desc += "**변경 내용:** 웹훅이 생성, 수정 또는 삭제되었습니다.\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in channel.guild.audit_logs(
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.action in [discord.AuditLogAction.webhook_create, 
                               discord.AuditLogAction.webhook_update, 
                               discord.AuditLogAction.webhook_delete]:
                actor = entry.user.mention
                if entry.action == discord.AuditLogAction.webhook_create:
                    desc = f"**채널:** {channel.mention}\n**웹훅 생성**\n"
                    if hasattr(entry.target, 'name'):
                        desc += f"**이름:** `{entry.target.name}`\n"
                elif entry.action == discord.AuditLogAction.webhook_delete:
                    desc = f"**채널:** {channel.mention}\n**웹훅 삭제**\n"
                else:
                    desc = f"**채널:** {channel.mention}\n**웹훅 수정**\n"
                break
    except:
        pass
    
    desc += f"**수행자:** {actor}"
    
    await send_log(channel.guild, "웹훅 변경", desc, 0xe67e22, log_type="server")

# ------------------------------------------------
# 봇/통합 추가 로그
# ------------------------------------------------
@bot.event
async def on_guild_integrations_update(guild):
    desc = "서버의 통합(Integration) 설정이 변경되었습니다.\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(
            action=discord.AuditLogAction.integration_create,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            actor = entry.user.mention
            break
    except:
        pass
    
    desc += f"**수행자:** {actor}"
    
    await send_log(guild, "통합 설정 변경", desc, 0x3498db, log_type="server")

# ------------------------------------------------
# 스레드 생성 로그
# ------------------------------------------------
@bot.event
async def on_thread_create(thread):
    desc = f"**스레드:** {thread.mention} (`{thread.id}`)\n"
    desc += f"**부모 채널:** <#{thread.parent_id}>\n"
    desc += f"**생성자:** {thread.owner.mention if thread.owner else '알 수 없음'}\n"
    desc += f"**타입:** {'공개' if not thread.locked else '잠김'}\n"
    
    if thread.auto_archive_duration:
        desc += f"**자동 보관:** {thread.auto_archive_duration}분\n"
    
    await send_log(thread.guild, "스레드 생성", desc, 0x3498db, log_type="server")

# ------------------------------------------------
# 스레드 삭제 로그
# ------------------------------------------------
@bot.event
async def on_thread_delete(thread):
    desc = f"**스레드 이름:** `{thread.name}`\n"
    desc += f"**스레드 ID:** `{thread.id}`\n"
    desc += f"**부모 채널:** <#{thread.parent_id}>\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in thread.guild.audit_logs(
            action=discord.AuditLogAction.thread_delete,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == thread.id:
                actor = entry.user.mention
                break
    except:
        pass
    
    desc += f"**삭제자:** {actor}"
    
    await send_log(thread.guild, "스레드 삭제", desc, 0xe74c3c, log_type="server")

# ------------------------------------------------
# 스레드 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_thread_update(before, after):
    changes = []
    
    if before.name != after.name:
        changes.append(f"**이름:** `{before.name}` → `{after.name}`")
    if before.archived != after.archived:
        changes.append(f"**보관 상태:** {before.archived} → {after.archived}")
    if before.locked != after.locked:
        changes.append(f"**잠금 상태:** {before.locked} → {after.locked}")
    if before.auto_archive_duration != after.auto_archive_duration:
        changes.append(f"**자동 보관 시간:** {before.auto_archive_duration}분 → {after.auto_archive_duration}분")
    
    if not changes:
        return
    
    details = "\n".join(changes)
    
    await send_log(
        after.guild,
        "스레드 수정",
        f"**스레드:** {after.mention}\n{details}",
        0xf39c12
    )

# ------------------------------------------------
# 예약된 이벤트 생성 로그
# ------------------------------------------------
@bot.event
async def on_scheduled_event_create(event):
    desc = f"**이벤트 이름:** `{event.name}`\n"
    desc += f"**생성자:** {event.creator.mention if event.creator else '알 수 없음'}\n"
    desc += f"**시작 시간:** <t:{int(event.start_time.timestamp())}:F>\n"
    
    if event.end_time:
        desc += f"**종료 시간:** <t:{int(event.end_time.timestamp())}:F>\n"
    
    if event.description:
        desc += f"**설명:** {event.description[:200]}\n"
    
    if event.location:
        desc += f"**위치:** {event.location}\n"
    
    await send_log(event.guild, "이벤트 생성", desc, 0x2ecc71, log_type="server")

# ------------------------------------------------
# 예약된 이벤트 삭제 로그
# ------------------------------------------------
@bot.event
async def on_scheduled_event_delete(event):
    desc = f"**이벤트 이름:** `{event.name}`\n"
    desc += f"**이벤트 ID:** `{event.id}`\n"
    
    actor = "알 수 없음"
    await asyncio.sleep(1.2)
    try:
        async for entry in event.guild.audit_logs(
            action=discord.AuditLogAction.scheduled_event_delete,
            limit=1,
            after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
        ):
            if entry.target.id == event.id:
                actor = entry.user.mention
                break
    except:
        pass
    
    desc += f"**삭제자:** {actor}"
    
    await send_log(event.guild, "이벤트 삭제", desc, 0xe74c3c, log_type="server")

# ------------------------------------------------
# 예약된 이벤트 업데이트 로그
# ------------------------------------------------
@bot.event
async def on_scheduled_event_update(before, after):
    changes = []
    
    if before.name != after.name:
        changes.append(f"**이름:** `{before.name}` → `{after.name}`")
    if before.description != after.description:
        changes.append(f"**설명 변경됨**")
    if before.start_time != after.start_time:
        changes.append(f"**시작 시간:** <t:{int(before.start_time.timestamp())}:F> → <t:{int(after.start_time.timestamp())}:F>")
    if before.end_time != after.end_time:
        if after.end_time:
            changes.append(f"**종료 시간 변경됨**")
    if before.status != after.status:
        changes.append(f"**상태:** {str(before.status)} → {str(after.status)}")
    if before.location != after.location:
        changes.append(f"**위치:** {before.location or '없음'} → {after.location or '없음'}")
    
    if not changes:
        return
    
    details = "\n".join(changes)
    
    await send_log(
        after.guild,
        "이벤트 수정",
        f"**이벤트:** `{after.name}`\n{details}",
        0xf39c12
    )

# ------------------------------------------------
# 오토모드 규칙 실행 로그
# ------------------------------------------------
@bot.event
async def on_automod_action(execution):
    desc = f"**규칙 이름:** `{execution.rule_name}`\n"
    desc += f"**대상 유저:** <@{execution.user_id}> (`{execution.user_id}`)\n"
    desc += f"**채널:** <#{execution.channel_id}>\n"
    desc += f"**조치 유형:** {str(execution.action.type).replace('_', ' ').title()}\n"
    
    if execution.content:
        desc += f"**감지된 내용:** ```{execution.content[:200]}```\n"
    
    if execution.matched_keyword:
        desc += f"**매칭된 키워드:** `{execution.matched_keyword}`\n"
    
    await send_log(
        execution.guild,
        "오토모드 규칙 실행",
        desc,
        0xe74c3c
    )

# ============================================
# 오류 테스트 명령어
# ============================================
@bot.tree.command(name="오류-테스트", description="(개발자 전용) 오류로그가 잘 가는지 테스트합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def error_test(inter: discord.Interaction):
    """의도적으로 오류를 발생시켜 오류 로그 시스템을 테스트합니다."""
    try:
        await inter.response.defer(ephemeral=True)
        
        # 테스트 오류 메시지 전송
        test_exception = ValueError("이것은 오류 로그 시스템 테스트입니다")
        await send_error_log(
            "오류 로그 시스템 테스트",
            f"테스트 실행자: {inter.user.name} ({inter.user.id})\n서버: {inter.guild.name} ({inter.guild.id})",
            test_exception,
            interaction=inter
        )
        
        await safe_interaction_send(inter, "테스트 완료! 오류 메시지 채널을 확인하세요.", ephemeral=True)
    except Exception as e:
        try:
            await send_error_log("오류-테스트 명령어 실행 오류", f"사용자: {inter.user.name} ({inter.user.id})", e, interaction=inter)
        except:
            pass
        if not inter.response.is_done():
            await safe_interaction_send(inter, "테스트 중 오류가 발생했습니다.", ephemeral=True)
        else:
            await safe_interaction_send(inter, "테스트 중 오류가 발생했습니다.", ephemeral=True)
    
# ===============================
# 신뢰 멤버 및 경계 멤버 시스템
# ===============================
@bot.tree.command(name="신뢰멤버_설정", description="관리자 권한 없이도 봇 설정을 할 수 있는 신뢰 멤버를 추가합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def add_trusted_member(inter: discord.Interaction, member: discord.Member):
    if not inter.user.guild_permissions.administrator and inter.user.id not in SPECIAL_USER_ID:
        return await safe_interaction_send(inter, "서버 관리자만 사용할 수 있습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    if member.id in cfg.get("trusted_members", []):
        return await safe_interaction_send(inter, f"{member.mention} 님은 이미 신뢰 멤버입니다.", ephemeral=True)
    cfg.setdefault("trusted_members", []).append(member.id)
    save_configs(configs)
    await log_setting_change(inter, "신뢰 멤버 추가", f"{member.mention} 님이 신뢰 멤버로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님이 신뢰 멤버로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="신뢰멤버_제거", description="신뢰 멤버를 제거합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def remove_trusted_member(inter: discord.Interaction, member: discord.Member):
    if not inter.user.guild_permissions.administrator and inter.user.id not in SPECIAL_USER_ID:
        return await safe_interaction_send(inter, "서버 관리자만 사용할 수 있습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    if member.id not in cfg.get("trusted_members", []):
        return await safe_interaction_send(inter, f"{member.mention} 님은 신뢰 멤버가 아닙니다.", ephemeral=True)
    cfg["trusted_members"].remove(member.id)
    save_configs(configs)
    await log_setting_change(inter, "신뢰 멤버 제거", f"{member.mention} 님이 신뢰 멤버에서 제거되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님이 신뢰 멤버에서 제거되었습니다.", ephemeral=True)

@bot.tree.command(name="경계멤버_설정", description="특정 멤버를 경계 멤버로 설정/해제합니다. (신뢰 멤버 및 서버장 전용)")
async def toggle_watched_member(inter: discord.Interaction, member: discord.Member):
    if not is_trusted_or_owner(inter):
        return await safe_interaction_send(inter, "신뢰 멤버 또는 서버장만 사용할 수 있습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    watched = cfg.setdefault("watched_members", [])
    if member.id in watched:
        watched.remove(member.id)
        status = "해제"
    else:
        watched.append(member.id)
        status = "설정"
    save_configs(configs)
    await log_setting_change(inter, f"경계 멤버 {status}", f"{member.mention} 님이 경계 멤버로 {status}되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님이 경계 멤버로 **{status}**되었습니다.", ephemeral=True)

@bot.tree.command(name="경계멤버_확인", description="현재 서버의 경계 멤버 목록을 확인합니다.")
async def list_watched_members(inter: discord.Interaction):
    if not is_trusted_or_owner(inter):
        return await safe_interaction_send(inter, "신뢰 멤버 또는 서버장만 사용할 수 있습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    watched = cfg.get("watched_members", [])
    if not watched:
        return await safe_interaction_send(inter, "현재 설정된 경계 멤버가 없습니다.", ephemeral=True)
    mentions = [f"<@{uid}>" for uid in watched]
    embed = discord.Embed(title="경계 멤버 목록", description="\n".join(mentions), color=0xe67e22)
    await safe_interaction_send(inter, embed=embed, ephemeral=True)

# ===============================
# 로그 채널 세분화 설정
# ===============================
@bot.tree.command(name="로그채널설정_메시지", description="메시지(삭제/수정) 로그 채널을 설정합니다.")
async def set_message_log_channel(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter): return await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    cfg["message_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "메시지 로그 채널 변경", f"메시지 로그 채널이 {channel.mention}(으)로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 메시지 로그 채널이 {channel.mention}(으)로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="로그채널설정_유저", description="유저(닉네임/역할/보이스) 로그 채널을 설정합니다.")
async def set_user_log_channel(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter): return await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    cfg["user_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "유저 로그 채널 변경", f"유저 로그 채널이 {channel.mention}(으)로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 유저 로그 채널이 {channel.mention}(으)로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="로그채널설정_서버", description="서버(채널/역할/이모지 등) 로그 채널을 설정합니다.")
async def set_server_log_channel(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter): return await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True)
    cfg = get_config(inter.guild.id)
    cfg["server_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "서버 로그 채널 변경", f"서버 로그 채널이 {channel.mention}(으)로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 서버 로그 채널이 {channel.mention}(으)로 설정되었습니다.", ephemeral=True)

@bot.tree.command(name="로그채널설정_경계멤버", description="경계 멤버 활동 로그 채널을 설정합니다.")
async def set_watched_log_channel(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter):
        return await safe_interaction_send(inter, "권한이 없습니다.", ephemeral=True)

    cfg = get_config(inter.guild.id)
    cfg["watched_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "경계 멤버 로그 채널 변경", f"경계 멤버 로그 채널이 {channel.mention}(으)로 설정되었습니다.")

    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 경계 멤버 로그 채널이 {channel.mention}(으)로 설정되었습니다.", ephemeral=True)

# ===============================
# 서버장 DM 알림
# ===============================
@bot.tree.command(name="알림-서버장디엠", description="(개발자 전용) 봇이 참가된 모든 서버의 서버장에게 DM을 보냅니다.")
async def notify_owners_dm(inter: discord.Interaction, 내용: str):
    if inter.user.id not in SPECIAL_USER_ID:
        return await inter.response.send_message("개발자 전용 명령어입니다.", ephemeral=True)
    await inter.response.defer(ephemeral=True)
    success = 0
    fail = 0
    for guild in bot.guilds:
        try:
            owner = guild.owner or await guild.fetch_owner()
            if owner:
                embed = discord.Embed(title="서린 봇 공지사항", description=내용, color=0x3498db)
                embed.set_footer(text="서린 봇 개발팀")
                await owner.send(embed=embed)
                success += 1
        except:
            fail += 1
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 서버장 DM 전송 완료! (성공: {success}명, 실패: {fail}명)", ephemeral=True)

# ===============================
# 처벌 로그 시스템
# ===============================
@bot.tree.command(name="처벌로그채널설정", description="처벌 기록이 공개적으로 기록될 채널을 설정합니다.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def set_punishment_log_channel(inter: discord.Interaction, channel: discord.TextChannel):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members:
        return await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True)
    
    cfg = get_config(inter.guild.id)
    cfg["punishment_log_channel"] = channel.id
    save_configs(configs)
    await log_setting_change(inter, "처벌 로그 채널 변경", f"처벌 로그 채널이 {channel.mention} 으로 설정되었습니다.")
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> 처벌 로그 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True)

async def record_punishment(guild: discord.Guild, moderator: discord.Member, target: discord.Member, punishment_type: str, reason: str):
    """처벌 이력을 기록하고 로그 채널에 표시합니다."""
    cfg = get_config(guild.id)
    
    # 처벌 기록 저장
    user_id_str = str(target.id)
    if user_id_str not in cfg.get("punishments", {}):
        cfg["punishments"][user_id_str] = []
    
    punishment_record = {
        "moderator_id": moderator.id,
        "type": punishment_type,
        "reason": reason,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    cfg["punishments"][user_id_str].append(punishment_record)
    save_configs(configs)
    
    # 처벌 로그 채널에 전송
    punishment_log_channel_id = cfg.get("punishment_log_channel")
    if punishment_log_channel_id:
        channel = guild.get_channel(punishment_log_channel_id)
        if channel and isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).embed_links:
            embed = discord.Embed(
                title=f"✅ {punishment_type} 처벌 적용",
                color=0xe74c3c,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="대상", value=f"{target.mention} ({target.id})", inline=False)
            embed.add_field(name="처벌 유형", value=f"`{punishment_type}`", inline=True)
            embed.add_field(name="사유", value=f"`{reason}`", inline=False)
            embed.add_field(name="담당자", value=f"{moderator.mention}", inline=True)
            embed.set_thumbnail(url=target.display_avatar.url)
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

@bot.tree.command(name="처벌-경고", description="대상 멤버를 경고합니다 (공개 로그 기록).")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def punishment_warn(inter: discord.Interaction, member: discord.Member, *, reason: str = "사유 없음"):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members:
        return await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True)
    
    if member.id == inter.user.id:
        return await safe_interaction_send(inter, "자신에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    if member.top_role >= inter.user.top_role and member.id != inter.guild.owner_id:
        return await safe_interaction_send(inter, "자신보다 상위 역할의 멤버에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    # DM 발송
    try:
        await member.send(f"**{inter.guild.name}** 서버에서 **경고**를 받았습니다.\n**사유:** {reason}")
    except discord.Forbidden:
        pass
    
    # 처벌 기록
    await record_punishment(inter.guild, inter.user, member, "경고", reason)
    await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님에게 **경고**를 부여했습니다.", ephemeral=False)

@bot.tree.command(name="처벌-타임아웃", description="대상 멤버를 타임아웃합니다 (공개 로그 기록).")
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def punishment_timeout(inter: discord.Interaction, member: discord.Member, minutes: int = 5, *, reason: str = "사유 없음"):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.moderate_members:
        return await safe_interaction_send(inter, "멤버 제재 권한이 필요합니다.", ephemeral=True)
    
    if member.id == inter.user.id:
        return await safe_interaction_send(inter, "자신에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    if member.top_role >= inter.user.top_role and member.id != inter.guild.owner_id:
        return await safe_interaction_send(inter, "자신보다 상위 역할의 멤버에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    if minutes < 1:
        return await safe_interaction_send(inter, "시간은 1분 이상이어야 합니다.", ephemeral=True)
    
    if minutes > 40320:  # 28일
        minutes = 40320
    
    try:
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        
        # DM 발송
        try:
            await member.send(f"**{inter.guild.name}** 서버에서 **{minutes}분 타임아웃**을 받았습니다.\n**사유:** {reason}")
        except discord.Forbidden:
            pass
        
        # 처벌 기록
        await record_punishment(inter.guild, inter.user, member, f"타임아웃 ({minutes}분)", reason)
        await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님을 **{minutes}분 타임아웃** 처리했습니다.", ephemeral=False)
    except discord.Forbidden:
        await safe_interaction_send(inter, "❌ 봇 권한이 부족합니다.", ephemeral=True)
    except Exception as e:
        await safe_interaction_send(inter, f"❌ 타임아웃 처리 중 오류 발생: {e}", ephemeral=True)

@bot.tree.command(name="처벌-킥", description="대상 멤버를 추방합니다 (공개 로그 기록).")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def punishment_kick(inter: discord.Interaction, member: discord.Member, *, reason: str = "사유 없음"):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members:
        return await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True)
    
    if member.id == inter.user.id:
        return await safe_interaction_send(inter, "자신에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    if member.top_role >= inter.user.top_role and member.id != inter.guild.owner_id:
        return await safe_interaction_send(inter, "자신보다 상위 역할의 멤버에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    try:
        # DM 발송
        try:
            await member.send(f"**{inter.guild.name}** 서버에서 **추방**되었습니다.\n**사유:** {reason}")
        except discord.Forbidden:
            pass
        
        await member.kick(reason=reason)
        
        # 처벌 기록
        await record_punishment(inter.guild, inter.user, member, "추방 (킥)", reason)
        await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님을 **추방**했습니다.", ephemeral=False)
    except discord.Forbidden:
        await safe_interaction_send(inter, "❌ 봇 권한이 부족합니다.", ephemeral=True)
    except Exception as e:
        await safe_interaction_send(inter, f"❌ 추방 처리 중 오류 발생: {e}", ephemeral=True)

@bot.tree.command(name="밴", description="대상 멤버를 차단합니다 (공개 로그 기록).")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def punishment_ban(inter: discord.Interaction, member: discord.Member, *, reason: str = "사유 없음"):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.ban_members:
        return await safe_interaction_send(inter, "멤버 차단 권한이 필요합니다.", ephemeral=True)
    
    if member.id == inter.user.id:
        return await safe_interaction_send(inter, "자신에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    if member.top_role >= inter.user.top_role and member.id != inter.guild.owner_id:
        return await safe_interaction_send(inter, "자신보다 상위 역할의 멤버에게 처벌을 할 수 없습니다.", ephemeral=True)
    
    try:
        # DM 발송
        try:
            await member.send(f"**{inter.guild.name}** 서버에서 **차단**되었습니다.\n**사유:** {reason}")
        except discord.Forbidden:
            pass
        
        await member.ban(reason=reason, delete_message_seconds=60)
        
        # 처벌 기록
        await record_punishment(inter.guild, inter.user, member, "차단 (밴)", reason)
        await safe_interaction_send(inter, f"<a:check:1487718457662378064> {member.mention} 님을 **차단**했습니다.", ephemeral=False)
    except discord.Forbidden:
        await safe_interaction_send(inter, "❌ 봇 권한이 부족합니다.", ephemeral=True)
    except Exception as e:
        await safe_interaction_send(inter, f"❌ 차단 처리 중 오류 발생: {e}", ephemeral=True)

@bot.tree.command(name="처벌로그", description="특정 멤버의 처벌 기록을 확인합니다.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def view_punishment_log(inter: discord.Interaction, member: Optional[discord.Member] = None):
    if not check_admin_or_special(inter) and not inter.user.guild_permissions.kick_members:
        return await safe_interaction_send(inter, "멤버 추방 권한이 필요합니다.", ephemeral=True)
    
    await inter.response.defer(ephemeral=True, thinking=True)
    cfg = get_config(inter.guild.id)
    
    if member:
        # 특정 멤버의 처벌 기록
        user_id_str = str(member.id)
        punishments = cfg.get("punishments", {}).get(user_id_str, [])
        
        if not punishments:
            await safe_interaction_send(inter, f"{member.mention} 님의 처벌 기록이 없습니다.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"처벌 기록 - {member.display_name}",
            description=f"**UID:** {member.id}",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # 처벌 기록 입력 (최대 10개까지만 표시)
        for idx, punishment in enumerate(reversed(punishments[-10:]), 1):
            timestamp = punishment.get("timestamp", "알 수 없음")
            punish_type = punishment.get("type", "미기록")
            reason = punishment.get("reason", "사유 없음")
            
            embed.add_field(
                name=f"#{len(punishments) - idx + 1} - {punish_type}",
                value=f"**시간:** {timestamp}\n**사유:** {reason}",
                inline=False
            )
        
        embed.set_footer(text=f"총 {len(punishments)}개의 처벌 기록")
        await safe_interaction_send(inter, embed=embed, ephemeral=True)
    else:
        # 전체 처벌 통계
        all_punishments = cfg.get("punishments", {})
        
        if not all_punishments:
            await safe_interaction_send(inter, "서버의 처벌 기록이 없습니다.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="처벌 통계",
            color=0xe74c3c
        )
        
        # 가장 많은 처벌을 받은 멤버 TOP 10
        punishment_counts = [(uid, len(records)) for uid, records in all_punishments.items()]
        punishment_counts.sort(key=lambda x: x[1], reverse=True)
        
        top_text = ""
        for idx, (uid, count) in enumerate(punishment_counts[:10], 1):
            try:
                user = await inter.client.fetch_user(int(uid))
                top_text += f"{idx}. {user.mention} (`{uid}`): **{count}회**\n"
            except:
                top_text += f"{idx}. ID `{uid}`: **{count}회**\n"
        
        embed.add_field(name="가장 많은 처벌을 받은 멤버", value=top_text or "데이터 없음", inline=False)
        embed.add_field(name="총 처벌 기록", value=f"{len(all_punishments)}명", inline=True)
        
        # 처벌 유형별 통계
        punishment_type_counts = {}
        for records in all_punishments.values():
            for record in records:
                punish_type = record.get("type", "미기록")
                punishment_type_counts[punish_type] = punishment_type_counts.get(punish_type, 0) + 1
        
        type_text = "\n".join([f"`{ptype}`: {count}회" for ptype, count in sorted(punishment_type_counts.items(), key=lambda x: x[1], reverse=True)])
        embed.add_field(name="처벌 유형별 통계", value=type_text or "데이터 없음", inline=False)
        
        await safe_interaction_send(inter, embed=embed, ephemeral=True)


# 🔧 수정 9: 봇 토큰 환경변수로 변경 (보안 강화)
token = os.getenv("DISCORD_BOT_TOKEN", "")
if not token:
    print("❌ 오류: DISCORD_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
    print("시스템 환경변수 또는 .env 파일에서 토큰을 설정해주세요.")
else:
    bot.run(token)