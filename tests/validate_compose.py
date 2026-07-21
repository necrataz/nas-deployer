#!/usr/bin/env python3
"""验证内嵌 docker-compose.yml 的语法 + 端口冲突 + Profile 一致性

CI / pre-build 都跑这个, 不依赖外部服务
"""
import sys
import os

# 让脚本能从 src/ 目录导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compose_data import DOCKER_COMPOSE_YML  # noqa: E402
import yaml  # noqa: E402


def validate_yaml():
    """YAML 必须能解析"""
    services = yaml.safe_load(DOCKER_COMPOSE_YML).get("services", {})
    print(f"✅ YAML OK: {len(services)} 个服务")
    return services


def validate_no_port_conflicts(services):
    """端口必须唯一 (host 网络容器除外, 同一服务多次声明同一端口合法)"""
    port_map = {}
    for name, svc in services.items():
        # 跳过 host 网络容器 (Lucky)
        if svc.get("network_mode") == "host":
            continue
        for p in svc.get("ports", []):
            p_str = str(p)
            if ":" in p_str:
                host_port = p_str.split(":")[0]
                # 同一服务多次声明同一端口合法 (TCP + UDP 协议不同但端口号一样)
                port_map.setdefault(host_port, set()).add(name)

    conflicts = {p: v for p, v in port_map.items() if len(v) > 1}
    if conflicts:
        print(f"❌ 端口冲突:")
        for port, svcs in conflicts.items():
            print(f"   端口 {port}: {', '.join(svcs)}")
        sys.exit(1)
    print(f"✅ 无端口冲突: {len(port_map)} 个唯一端口")


def validate_profiles(services):
    """每个服务必须有 profiles 字段 (至少包含 'all' 和一个 category)"""
    profiles_seen = set()
    for name, svc in services.items():
        profs = svc.get("profiles", [])
        if not profs:
            print(f"❌ 服务 '{name}' 缺 profiles 字段")
            sys.exit(1)
        profiles_seen.update(profs)

    expected = {"movie", "read", "pt", "nav", "ai", "draw", "news", "tv", "tools", "all"}
    missing = expected - profiles_seen
    if missing:
        print(f"❌ 缺失 profile: {missing}")
        sys.exit(1)
    print(f"✅ Profile 一致: {sorted(profiles_seen)}")


def validate_apps_metadata():
    """apps.py 里所有引用的 app 必须存在, profile 必须存在"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from apps import APPS, PROFILES

    # 所有 profile 里的 app 必须存在于 APPS
    for prof, data in PROFILES.items():
        for app in data["apps"]:
            if app not in APPS:
                print(f"❌ profile '{prof}' 引用不存在的 app: {app}")
                sys.exit(1)

    # 所有 APPS 的 profile 字段必须在 PROFILES
    for app_key, app_data in APPS.items():
        if app_data["profile"] not in PROFILES:
            print(f"❌ app '{app_key}' 引用不存在的 profile: {app_data['profile']}")
            sys.exit(1)

    print(f"✅ apps.py 元数据一致: {len(APPS)} apps, {len(PROFILES)} profiles")


if __name__ == "__main__":
    services = validate_yaml()
    validate_no_port_conflicts(services)
    validate_profiles(services)
    validate_apps_metadata()
    print("\n🎉 全部验证通过")