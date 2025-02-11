<script>
    import { onMount } from 'svelte';
  
    // Function to handle the signing process with Amber
    function handleSignEvent(eventJson) {
      const callbackUrl = 'https://example.com/?event='; // Replace with your callback URL
      const encodedJson = encodeURIComponent(JSON.stringify(eventJson));
  
      window.location.href = `nostrsigner:${encodedJson}?compressionType=none&returnType=signature&type=sign_event&callbackUrl=${callbackUrl}`;
    }
  
    // Sample event to be signed
    let eventToSign = {
      kind: 1,
      content: 'Test content'
    };
  
    onMount(() => {
      const urlParams = new URLSearchParams(window.location.search);
      const eventResult = urlParams.get('event');
      if (eventResult) {
        alert(`Signed Event: ${eventResult}`);
      }
    });
  </script>
  
  <main>
    <h1>NOSTR Amber Signer Integration</h1>
    <button on:click={() => handleSignEvent(eventToSign)}>Sign Event with Amber</button>
  </main>