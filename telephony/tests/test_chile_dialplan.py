import pytest
from telephony.telephony_engine.chile_dialplan_validator import ChileDialplanValidator, PhoneNumberType


def test_validate_chilean_mobile():
    # Formato E.164
    info1 = ChileDialplanValidator.analyze_number("+56912345678")
    assert info1.is_valid is True
    assert info1.number_type == PhoneNumberType.MOBILE
    assert info1.digits_9 == "912345678"
    assert info1.e164 == "+56912345678"

    # Formato 9 dígitos
    info2 = ChileDialplanValidator.analyze_number("987654321")
    assert info2.is_valid is True
    assert info2.number_type == PhoneNumberType.MOBILE
    assert info2.e164 == "+56987654321"

    # Formato con espacios y guiones
    info3 = ChileDialplanValidator.analyze_number("+56 9 8888-9999")
    assert info3.is_valid is True
    assert info3.digits_9 == "988889999"


def test_validate_santiago_landline():
    # 22 Santiago
    info1 = ChileDialplanValidator.analyze_number("+56221234567")
    assert info1.is_valid is True
    assert info1.number_type == PhoneNumberType.LANDLINE
    assert info1.region == "Región Metropolitana (Santiago)"
    assert info1.digits_9 == "221234567"

    # 23 Santiago
    info2 = ChileDialplanValidator.analyze_number("239876543")
    assert info2.is_valid is True
    assert info2.number_type == PhoneNumberType.LANDLINE


def test_validate_regional_landlines():
    # Valparaíso (32)
    info_valpo = ChileDialplanValidator.analyze_number("+56322123456")
    assert info_valpo.is_valid is True
    assert "Valparaíso" in (info_valpo.region or "")

    # Concepción / Biobío (41)
    info_concep = ChileDialplanValidator.analyze_number("+56412123456")
    assert info_concep.is_valid is True
    assert "Biobío" in (info_concep.region or "")


def test_validate_emergency_numbers():
    samu = ChileDialplanValidator.analyze_number("131")
    assert samu.is_valid is True
    assert samu.number_type == PhoneNumberType.EMERGENCY
    assert "SAMU" in samu.description

    bomberos = ChileDialplanValidator.analyze_number("132")
    assert bomberos.is_valid is True
    assert bomberos.number_type == PhoneNumberType.EMERGENCY

    carabineros = ChileDialplanValidator.analyze_number("133")
    assert carabineros.is_valid is True
    assert carabineros.number_type == PhoneNumberType.EMERGENCY


def test_to_sip_uri():
    uri_mob = ChileDialplanValidator.to_sip_uri("912345678", "zadarma_endpoint")
    assert uri_mob == "PJSIP/+56912345678@zadarma_endpoint"

    uri_emerg = ChileDialplanValidator.to_sip_uri("133", "redvoiss_endpoint")
    assert uri_emerg == "PJSIP/133@redvoiss_endpoint"
