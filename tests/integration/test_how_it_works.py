def test_how_it_works_page_and_home_anonymous(client):
    # GET the public how-it-works page
    r = client.get('/how-it-works')
    assert r.status_code == 200
    assert b"How Meutch works" in r.data or b"Why we built Meutch" in r.data

    # GET the homepage as anonymous and verify the prominent CTA exists
    r2 = client.get('/')
    assert r2.status_code == 200
    assert b"Learn more about how it works" in r2.data
