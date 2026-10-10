import pytest

from app.estate import (AccessRule, AppManifest, Dataset, Dependency, Interface, ManifestRejected,
                        estate_edges, observed_inputs)
from app.export import GeneratedAgent, register_export

from conftest import FakeGovernance

CLIENTS = Dataset("postgres://crm", "clients", frozenset({"client-data"}), "crm-readonly")


def manifest(**over):
    base = dict(app_id="calls-log", name="Calls log", owner="team-ops", accountable_person="alice",
                namespace="ops", environment="prod", inputs=[CLIENTS],
                outputs=[Dataset("app://calls-log", "calls", frozenset({"client-data"}))],
                exposes=[Interface("calls-api", "api")],
                depends_on=[Dependency("client-lookup", "search-api")],
                access=[AccessRule("grp-ops-desk", "user")])
    base.update(over)
    return AppManifest(**base)


def test_valid_manifest_goes_into_the_card():
    gov = FakeGovernance()
    agent = GeneratedAgent("calls-log", "Calls log", "d", "1.0.0", "team-ops", "alice", "medium", "ops",
                           "sess-1", "app")
    card = register_export(gov, agent, "https://apps/calls-log", manifest())
    params = card["capabilities"]["extensions"][0]["params"]
    assert params["dataClasses"] == ["client-data"]
    assert params["app"]["access"] == [{"entraGroup": "grp-ops-desk", "role": "user"}]
    assert params["app"]["dependsOn"] == [{"appId": "client-lookup", "interface": "search-api"}]


def test_app_without_access_rules_is_refused():
    with pytest.raises(ManifestRejected):
        manifest(access=[]).validate()


def test_client_data_app_cannot_be_open_to_everyone():
    with pytest.raises(ManifestRejected):
        manifest(access=[AccessRule("everyone", "user")]).validate()


def test_outputs_keep_upstream_data_classes():
    with pytest.raises(ManifestRejected):
        manifest(outputs=[Dataset("app://calls-log", "calls")]).validate()


def test_failed_manifest_stops_export():
    gov = FakeGovernance()
    agent = GeneratedAgent("x", "x", "d", "1", "o", "a", "low", "ns", "s", "app")
    with pytest.raises(ManifestRejected):
        register_export(gov, agent, "u", manifest(access=[]))
    assert gov.cards == {}


def test_observed_reads_merge_and_feed_session_classes(make_ctx):
    ctx = make_ctx(FakeGovernance())
    ctx.record_read(CLIENTS)
    ctx.record_read(Dataset("postgres://crm", "clients", frozenset({"pii"})))
    merged = observed_inputs(ctx.reads)
    assert len(merged) == 1 and merged[0].data_classes == {"client-data", "pii"}
    assert {"client-data", "pii"} <= ctx.data.current


def test_estate_edges_connect_apps_and_data():
    edges = estate_edges([manifest()])
    assert ("postgres://crm/clients", "app://calls-log", "reads") in edges
    assert ("app://calls-log", "app://client-lookup", "calls") in edges


def test_openlineage_io_includes_app_dependencies():
    io = manifest().openlineage_io()
    assert {"namespace": "app://client-lookup", "name": "search-api"} in io["inputs"]
    assert {"namespace": "app://calls-log", "name": "calls-api"} in io["outputs"]
