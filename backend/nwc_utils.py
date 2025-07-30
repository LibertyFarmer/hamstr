# pip3 install websocket-client
from websocket import create_connection
import json
import base64
import time
import math
import hashlib
# pip3 install secp256k1
from secp256k1 import PrivateKey, PublicKey
# pip3 install pycryptodome==3.10.1
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util import Counter
import threading

BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
unpad = lambda s : s[:-ord(s[len(s)-1:])]

def encrypt( privkey, pubkey, plaintext ):
    key = PublicKey( bytes.fromhex( "02" + pubkey ), True ).tweak_mul( bytes.fromhex( privkey ) ).serialize().hex()[ 2: ]
    key_bytes = 32
    key = bytes.fromhex( key )
    plaintext = pad( plaintext )
    plaintext = plaintext.encode( "utf-8" )
    assert len( key ) == key_bytes

    # Choose a random, 16-byte IV.
    iv = Random.new().read( AES.block_size )

    # Create AES-CTR cipher.
    aes = AES.new( key, AES.MODE_CBC, iv )

    # Encrypt and return IV and ciphertext.
    ciphertext = aes.encrypt( plaintext )

    # Convert to base64
    cipher_b64 = base64.b64encode(ciphertext).decode( 'ascii' )
    cipher_iv = base64.b64encode(iv).decode( 'ascii' )

    return cipher_b64 + "?iv=" + cipher_iv

def decrypt( privkey, pubkey, ciphertext ):
    key = PublicKey( bytes.fromhex( "02" + pubkey ), True ).tweak_mul( bytes.fromhex( privkey ) ).serialize().hex()[ 2: ]
    key_bytes = 32
    key = bytes.fromhex( key )
    ( ciphertext, iv ) = ciphertext.split( "?iv=" )
    ciphertext = base64.b64decode( ciphertext.encode( 'ascii' ) )
    iv = base64.b64decode( iv.encode( 'ascii' ) )
    assert len( key ) == key_bytes

    # Create AES-CTR cipher.
    aes = AES.new( key, AES.MODE_CBC, iv )

    # Decrypt and return the plaintext.
    plaintext = aes.decrypt( ciphertext ).decode( 'ascii' )
    plaintext = unpad( plaintext )
    return plaintext

def sha256( text_to_hash ):
	m = hashlib.sha256()
	m.update(bytes(text_to_hash, 'UTF-8'))
	return m.digest().hex()

def processNWCstring( string ):
	if ( string[ 0:22 ] != "nostr+walletconnect://" ):
		print( 'Your pairing string was invalid, try one that starts with this: nostr+walletconnect://' )
		return
	string = string[ 22: ]
	arr = string.split( "&" )
	item = arr[ 0 ].split( "?" )
	del arr[ 0 ]
	arr.insert( 0, item[ 0 ] )
	arr.insert( 1, item[ 1 ] )
	arr[ 0 ] = "wallet_pubkey=" + arr[ 0 ]
	arr2 = []
	obj = {}
	for item in arr:
		item = item.split( "=" )
		arr2.append( item[ 0 ] )
		arr2.append( item[ 1 ] )
	for index, item in enumerate( arr2 ):
		if ( item == "secret" ):
			arr2[ index ] = "app_privkey"
	for index, item in enumerate( arr2 ):
		if ( index % 2 ):
			obj[ arr2[ index - 1 ] ] = item
	obj[ "app_pubkey" ] = PrivateKey( bytes.fromhex( obj[ "app_privkey" ] ) ).pubkey.serialize().hex()[ 2: ]
	return obj

def getEvents( relay, ids, kinds, until, since, limit, etags, ptags ):
    events = []
    subId = PrivateKey().serialize()[ 0:16 ]
    myfilter = {}
    if ( ids ):
        myfilter[ "ids" ] = ids
    if ( kinds ):
	    myfilter[ "kinds" ] = kinds
    if ( until ):
        myfilter[ "until" ] = until
    if ( since ):
        myfilter[ "since" ] = since
    if ( limit ):
        myfilter[ "limit" ] = limit
    if ( etags ):
        myfilter[ "#e" ] = etags
    if ( ptags ):
        myfilter[ "#p" ] = ptags
    subscription = [ "REQ", subId, myfilter ]
    ws = create_connection( relay )
    ws.send( json.dumps( subscription ) )
    for i in range( limit + 1 ):
        response = ws.recv()
        response = json.loads( response )
        if ( len( response ) < 3 ):
        	continue
        events.append( response[ 2 ] )
        ws.close()
    return events

def getResponse( nwc_obj, event_id, val ):
	relay = nwc_obj[ "relay" ]
	ids = None
	kinds = [ 23195 ]
	until = None
	since = None
	limit = 1
	etags = [ event_id ]
	ptags = [ nwc_obj[ "app_pubkey" ] ]
	events = []
	for i in [1,2,3,4,5,6,7]:
		if ( not len( events ) ):
			events2 = getEvents( relay, ids, kinds, until, since, limit, etags, ptags )
			if ( not not len( events2 ) ): events = events2
	if ( not not len( events ) ):
		val[ 0 ] = events[ 0 ]
		return
	val[ 0 ] = events
	return

def sendEvent( event, nwc_obj ):
    event_id = json.loads( event )[ 1 ][ "id" ]
    relay = nwc_obj[ "relay" ]
    response = None
    ws = create_connection( relay )
    ws.send( event )
    response = ws.recv()
    ws.close()
    return response

def getSignedEvent( event, privkey ):
    eventData = json.dumps([
        0,
        event['pubkey'],
        event['created_at'],
        event['kind'],
        event['tags'],
        event['content']
    ], separators=( ',', ':' ) )
    event[ "id" ] = sha256( eventData );
    privkey = PrivateKey( bytes.fromhex( privkey ) )
    event[ "sig" ] = privkey.schnorr_sign( bytes.fromhex( event[ "id" ] ), "none", True ).hex()
    return event

def makeInvoice( nwc_obj, amt, desc ):
    msg = json.dumps({
        "method": "make_invoice",
        "params": {
            "amount": amt * 1000,
            "description": desc,
        }
    })
    emsg = encrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], msg );
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [ [ "p", nwc_obj[ "wallet_pubkey" ] ] ],
        "created_at": math.floor( time.time() ),
        "pubkey": nwc_obj[ "app_pubkey" ],
    }
    event = getSignedEvent( obj, nwc_obj[ "app_privkey" ] )
    eid = event[ "id" ]
    event = json.dumps( ["EVENT", event], separators=( ',', ':' ) )
    val = [False]
    download_thread = threading.Thread( target=getResponse, name="Background", args=( nwc_obj, eid, val ) )
    download_thread.start()
    sendEvent( event, nwc_obj )
    for i in [1,2,3]:
    	if ( not val[ 0 ] ):
    		time.sleep( 1 )
    		continue
    response = val[ 0 ]
    ersp = response[ "content" ]
    drsp = decrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], ersp )
    dobj = json.loads( drsp )
    return dobj

def checkInvoice(nwc_obj, invoice=None, payment_hash=None):
    if invoice is None and payment_hash is None:
        raise ValueError("Either 'invoice' or 'payment_hash' must be provided")
    
    params = {}
    if invoice is not None:
        params["invoice"] = invoice
    if payment_hash is not None:
        params["payment_hash"] = payment_hash

    msg = json.dumps({
        "method": "lookup_invoice",
        "params": params
    })
    emsg = encrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], msg );
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [ [ "p", nwc_obj[ "wallet_pubkey" ] ] ],
        "created_at": math.floor( time.time() ),
        "pubkey": nwc_obj[ "app_pubkey" ],
    }
    event = getSignedEvent( obj, nwc_obj[ "app_privkey" ] )
    eid = event[ "id" ]
    event = json.dumps( ["EVENT", event], separators=( ',', ':' ) )
    val = [False]
    download_thread = threading.Thread( target=getResponse, name="Background", args=( nwc_obj, eid, val ) )
    download_thread.start()
    sendEvent( event, nwc_obj )
    for i in [1,2,3]:
    	if ( not val[ 0 ] ):
    		time.sleep( 1 )
    		continue
    response = val[ 0 ]
    ersp = response[ "content" ]
    drsp = decrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], ersp )
    dobj = json.loads( drsp )
    return dobj
    # an error looks like this:
    # {error: {code: "INTERNAL", message: "Something went wrong while looking up invoice: "}, result_type: "lookup_invoice"}

def didPaymentSucceed( nwc_obj, invoice ):
	invoice_info = checkInvoice( nwc_obj, invoice=invoice )
	if ( invoice_info and not ( "error" in invoice_info ) and ( "result" in invoice_info ) and ( "preimage" in invoice_info[ "result" ] ) ):
	    return invoice_info[ "result" ][ "preimage" ]
	return False

def tryToPayInvoice( nwc_obj, invoice, amnt = None ):
    msg = {
        "method": "pay_invoice",
        "params": {
            "invoice": invoice,
        }
    }
    if ( amnt ): msg[ "params" ][ "amount" ] = amnt
    msg = json.dumps( msg )
    emsg = encrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], msg );
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [ [ "p", nwc_obj[ "wallet_pubkey" ] ] ],
        "created_at": math.floor( time.time() ),
        "pubkey": nwc_obj[ "app_pubkey" ],
    }
    event = getSignedEvent( obj, nwc_obj[ "app_privkey" ] )
    eid = event[ "id" ]
    event = json.dumps( ["EVENT", event], separators=( ',', ':' ) )
    sendEvent( event, nwc_obj )

def getInfo( nwc_obj ):
    msg = {
        "method": "get_info"
    }
    msg = json.dumps( msg )
    emsg = encrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], msg );
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [ [ "p", nwc_obj[ "wallet_pubkey" ] ] ],
        "created_at": math.floor( time.time() ),
        "pubkey": nwc_obj[ "app_pubkey" ],
    }
    event = getSignedEvent( obj, nwc_obj[ "app_privkey" ] )
    eid = event[ "id" ]
    event = json.dumps( ["EVENT", event], separators=( ',', ':' ) )
    val = [False]
    download_thread = threading.Thread( target=getResponse, name="Background", args=( nwc_obj, eid, val ) )
    download_thread.start()
    sendEvent( event, nwc_obj )
    for i in [1,2,3]:
        if ( not val[ 0 ] ):
            time.sleep( 1 )
            continue
    response = val[ 0 ]
    ersp = response[ "content" ]
    drsp = decrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], ersp )
    dobj = json.loads( drsp )
    return dobj

def listTx( nwc_obj, params = {} ):
    msg = {
        "method": "list_transactions",
        "params": params
    }
    msg = json.dumps( msg )
    emsg = encrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], msg );
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [ [ "p", nwc_obj[ "wallet_pubkey" ] ] ],
        "created_at": math.floor( time.time() ),
        "pubkey": nwc_obj[ "app_pubkey" ],
    }
    event = getSignedEvent( obj, nwc_obj[ "app_privkey" ] )
    eid = event[ "id" ]
    event = json.dumps( ["EVENT", event], separators=( ',', ':' ) )
    val = [False]
    download_thread = threading.Thread( target=getResponse, name="Background", args=( nwc_obj, eid, val ) )
    download_thread.start()
    sendEvent( event, nwc_obj )
    for i in [1,2,3]:
        if ( not val[ 0 ] ):
            time.sleep( 1 )
            continue
    response = val[ 0 ]
    ersp = response[ "content" ]
    drsp = decrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], ersp )
    dobj = json.loads( drsp )
    return dobj


def getBalance( nwc_obj ):
    msg = {
        "method": "get_balance"
    }
    msg = json.dumps( msg )
    emsg = encrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], msg );
    obj = {
        "kind": 23194,
        "content": emsg,
        "tags": [ [ "p", nwc_obj[ "wallet_pubkey" ] ] ],
        "created_at": math.floor( time.time() ),
        "pubkey": nwc_obj[ "app_pubkey" ],
    }
    event = getSignedEvent( obj, nwc_obj[ "app_privkey" ] )
    eid = event[ "id" ]
    event = json.dumps( ["EVENT", event], separators=( ',', ':' ) )
    val = [False]
    download_thread = threading.Thread( target=getResponse, name="Background", args=( nwc_obj, eid, val ) )
    download_thread.start()
    sendEvent( event, nwc_obj )
    for i in [1,2,3]:
        if ( not val[ 0 ] ):
            time.sleep( 1 )
            continue
    response = val[ 0 ]
    ersp = response[ "content" ]
    drsp = decrypt( nwc_obj[ "app_privkey" ], nwc_obj[ "wallet_pubkey" ], ersp )
    dobj = json.loads( drsp )
    return dobj


# print( makeInvoice( processNWCstring( nwc_string ), 100, "test" ) )
# print( checkInvoice( processNWCstring( nwc_string ), invoice="lnbc1u1png6lw0pp5h4l73ajf4u548ktalztfwt7k9wtp9xhgqs6t0my0mw450nfkmnrsdq8w3jhxaqcqzzsxqyz5vqsp5asqxxjr2uhsfxyjwt2gxrq38dejkr76rmzl0zstjqlx8rrlcqpns9qxpqysgq22dwgadd7xnsnn8jzwkfxwy7nwclzt4d8wa3adrml83a0nvgy2hzm565k4qn0rcrzx7n2j8dszq9yqvhdx2z0xes77j5e480clx6d7cq2vvqj5" ) )
# print( didPaymentSucceed( processNWCstring( nwc_string ), "lnbc700n1pngmqvkpp57yg7u02n2pxack552mwdl5k8derwsyrgh2uft0lptqvcw8qv9l0qdpuge6kuerfdenjqsrnw4cx2un5v4ehgmn9wssx7m3qwd6xzcmtv4ezumn9waescqzzsxqrrsssp5uy70kfvlwfw4xhlu0k7hr7luq0qwgl5sdc9lyk4aqxvqzqqesjes9qyyssq9w7dyt6e64dyhws70qkvnauq59vmkh9lt4j5t598x3f7xzzv5edyg2g0rtdphtqmkqq3xja27kz4gvdgdy7qeymtms32d82gpmtekvspeyp4rq" ) )
# print( tryToPayInvoice( processNWCstring( nwc_string ), "lnbc700n1pngmqvkpp57yg7u02n2pxack552mwdl5k8derwsyrgh2uft0lptqvcw8qv9l0qdpuge6kuerfdenjqsrnw4cx2un5v4ehgmn9wssx7m3qwd6xzcmtv4ezumn9waescqzzsxqrrsssp5uy70kfvlwfw4xhlu0k7hr7luq0qwgl5sdc9lyk4aqxvqzqqesjes9qyyssq9w7dyt6e64dyhws70qkvnauq59vmkh9lt4j5t598x3f7xzzv5edyg2g0rtdphtqmkqq3xja27kz4gvdgdy7qeymtms32d82gpmtekvspeyp4rq" ) )
# print( listTx( processNWCstring( nwc_string, { "type": "outgoing"} ) ) )
# print( getBalance( processNWCstring( nwc_string ) ) )
