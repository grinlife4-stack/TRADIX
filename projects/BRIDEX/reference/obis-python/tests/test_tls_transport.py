import datetime as dt
import hashlib
import ipaddress
import ssl
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from obis_bridge import ALPN_PROTOCOL, TLS_PROFILE_ID, Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer


CLIENT_URI = "urn:obis:peer:11111111-1111-4111-8111-111111111111"
SERVER_URI = "urn:obis:peer:22222222-2222-4222-8222-222222222222"
OTHER_CLIENT_URI = "urn:obis:peer:33333333-3333-4333-8333-333333333333"
ECHO_CAPABILITY = "example.echo"
ECHO_VERSION = "1.0"


def create_ca(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OBIS Test CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True,
                crl_sign=True, encipher_only=None, decipher_only=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    ca_path = tmp_path / "ca.pem"
    ca_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert, ca_path


def create_leaf(tmp_path: Path, ca_key, ca_cert, peer_uri: str, *, server: bool, filename: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, filename)])
    san = [x509.UniformResourceIdentifier(peer_uri)]
    if server:
        san.extend([
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ])
    eku = ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=None, decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([eku]), critical=False)
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    cert_path = tmp_path / f"{filename}.crt.pem"
    key_path = tmp_path / f"{filename}.key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    return cert, cert_path, key_path, fingerprint


def server_context(ca_path: Path, cert_path: Path, key_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(cert_path), str(key_path))
    context.load_verify_locations(cafile=str(ca_path))
    context.verify_mode = ssl.CERT_REQUIRED
    context.set_alpn_protocols([ALPN_PROTOCOL])
    return context


def client_context(ca_path: Path, cert_path: Path | None, key_path: Path | None) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca_path))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    if cert_path is not None and key_path is not None:
        context.load_cert_chain(str(cert_path), str(key_path))
    context.set_alpn_protocols([ALPN_PROTOCOL])
    return context


def make_pair(tmp_path: Path):
    ca_key, ca_cert, ca_path = create_ca(tmp_path)
    _, server_cert, server_key, _ = create_leaf(tmp_path, ca_key, ca_cert, SERVER_URI, server=True, filename="server")
    _, client_cert, client_key, client_fingerprint = create_leaf(tmp_path, ca_key, ca_cert, CLIENT_URI, server=False, filename="client")
    peer = OBISPeer(
        SERVER_URI,
        credentials=[
            Credential(
                key_id="client-certificate-1",
                peer_id=CLIENT_URI,
                principal_ref="principal:client",
                secret=None,
                allowed_scopes=frozenset({"echo:read"}),
                certificate_uri=CLIENT_URI,
                certificate_sha256=client_fingerprint,
            )
        ],
    )
    peer.register_capability(ECHO_CAPABILITY, ECHO_VERSION, {"echo:read"}, lambda payload: {"echo": payload["value"]})
    client = OBISClient(
        CLIENT_URI, SERVER_URI, "client-certificate-1", "principal:client", None,
        {"echo:read"}, tls_context=client_context(ca_path, client_cert, client_key)
    )
    return peer, server_context(ca_path, server_cert, server_key), client, ca_key, ca_cert, ca_path, client_cert, client_key


def test_mtls_profile_direct_peer_request_succeeds_without_shared_hmac_secret(tmp_path: Path) -> None:
    peer, server_tls, client, *_ = make_pair(tmp_path)
    assert TLS_PROFILE_ID == "OBIS-TLS-MTLS-1"
    with OBISServer(peer, tls_context=server_tls) as server:
        response = client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "hello"})
    assert response["outcome"] == "succeeded"
    assert response["result"] == {"echo": "hello"}


def test_mtls_error_response_is_authenticated_by_tls_and_preserves_obis_error(tmp_path: Path) -> None:
    peer, server_tls, client, *_ = make_pair(tmp_path)
    client.scopes = frozenset({"echo:read", "echo:admin"})
    with OBISServer(peer, tls_context=server_tls) as server:
        with pytest.raises(OBISRequestError) as caught:
            client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "no"}, scopes={"echo:admin"})
    assert caught.value.code == "authorization.denied"


def test_mtls_rejects_client_certificate_not_bound_to_configured_peer(tmp_path: Path) -> None:
    ca_key, ca_cert, ca_path = create_ca(tmp_path)
    _, server_cert, server_key, _ = create_leaf(tmp_path, ca_key, ca_cert, SERVER_URI, server=True, filename="server")
    _, expected_cert, _, expected_fingerprint = create_leaf(tmp_path, ca_key, ca_cert, CLIENT_URI, server=False, filename="expected-client")
    _, other_cert, other_key, _ = create_leaf(tmp_path, ca_key, ca_cert, OTHER_CLIENT_URI, server=False, filename="other-client")
    peer = OBISPeer(
        SERVER_URI,
        credentials=[
            Credential(
                key_id="client-certificate-1",
                peer_id=CLIENT_URI,
                principal_ref="principal:client",
                secret=None,
                allowed_scopes=frozenset({"echo:read"}),
                certificate_uri=CLIENT_URI,
                certificate_sha256=expected_fingerprint,
            )
        ],
    )
    peer.register_capability(ECHO_CAPABILITY, ECHO_VERSION, {"echo:read"}, lambda payload: {"echo": payload["value"]})
    client = OBISClient(
        OTHER_CLIENT_URI, SERVER_URI, "client-certificate-1", "principal:client", None,
        {"echo:read"}, tls_context=client_context(ca_path, other_cert, other_key)
    )
    with OBISServer(peer, tls_context=server_context(ca_path, server_cert, server_key)) as server:
        with pytest.raises(OBISRequestError):
            client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})


def test_mtls_rejects_server_certificate_uri_mismatch(tmp_path: Path) -> None:
    peer, _, client, ca_key, ca_cert, ca_path, _, _ = make_pair(tmp_path)
    _, wrong_server_cert, wrong_server_key, _ = create_leaf(
        tmp_path, ca_key, ca_cert, OTHER_CLIENT_URI, server=True, filename="wrong-server"
    )
    wrong_context = server_context(ca_path, wrong_server_cert, wrong_server_key)
    with OBISServer(peer, tls_context=wrong_context) as server:
        with pytest.raises(OBISRequestError, match="server certificate peer identity"):
            client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})


def test_mtls_requires_client_certificate(tmp_path: Path) -> None:
    peer, server_tls, _, _, _, ca_path, _, _ = make_pair(tmp_path)
    no_certificate_client = OBISClient(
        CLIENT_URI, SERVER_URI, "client-certificate-1", "principal:client", None,
        {"echo:read"}, tls_context=client_context(ca_path, None, None)
    )
    with OBISServer(peer, tls_context=server_tls) as server:
        with pytest.raises(OBISRequestError, match="TLS peer connection"):
            no_certificate_client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})


def test_mtls_rejects_untrusted_server_ca(tmp_path: Path) -> None:
    peer, server_tls, _, _, _, _, client_cert, client_key = make_pair(tmp_path)
    wrong_ca_dir = tmp_path / "wrong-ca"
    _, _, wrong_ca_path = create_ca(wrong_ca_dir)
    untrusted_client = OBISClient(
        CLIENT_URI, SERVER_URI, "client-certificate-1", "principal:client", None,
        {"echo:read"}, tls_context=client_context(wrong_ca_path, client_cert, client_key)
    )
    with OBISServer(peer, tls_context=server_tls) as server:
        with pytest.raises(OBISRequestError, match="TLS peer connection"):
            untrusted_client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})


def test_mtls_contexts_must_be_tls13_and_server_must_require_client_cert() -> None:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    with pytest.raises(ValueError, match="TLS 1.3 only"):
        OBISClient(CLIENT_URI, SERVER_URI, "k", "p", None, {"echo:read"}, tls_context=context)

    server_context_without_mtls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context_without_mtls.minimum_version = ssl.TLSVersion.TLSv1_3
    server_context_without_mtls.maximum_version = ssl.TLSVersion.TLSv1_3
    with pytest.raises(ValueError, match="require client certificates"):
        OBISServer(OBISPeer(SERVER_URI), tls_context=server_context_without_mtls)


def test_mtls_endpoint_cannot_fall_back_to_plaintext_http(tmp_path: Path) -> None:
    _, _, client, *_ = make_pair(tmp_path)
    with pytest.raises(ValueError, match="HTTPS endpoint"):
        client.invoke("http://127.0.0.1:12345", ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})


def test_mtls_credential_revocation_blocks_subsequent_requests(tmp_path: Path) -> None:
    peer, server_tls, client, *_ = make_pair(tmp_path)
    assert peer.revoke_credential("client-certificate-1") is True
    assert peer.revoke_credential("client-certificate-1") is False
    with OBISServer(peer, tls_context=server_tls) as server:
        with pytest.raises(OBISRequestError):
            client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})



def test_mtls_rejects_connection_without_obis_alpn(tmp_path: Path) -> None:
    peer, server_tls, _, _, _, ca_path, client_cert, client_key = make_pair(tmp_path)
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca_path))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(client_cert), str(client_key))
    client = OBISClient(
        CLIENT_URI, SERVER_URI, "client-certificate-1", "principal:client", None,
        {"echo:read"}, tls_context=context
    )
    with OBISServer(peer, tls_context=server_tls) as server:
        with pytest.raises(OBISRequestError, match="ALPN protocol"):
            client.invoke(server.address, ECHO_CAPABILITY, ECHO_VERSION, {"value": "blocked"})
