export function shouldFinishGooglePlayTransaction(serverResponse) {
  // The backend owns Google Play consume/acknowledge. Calling native finish here would duplicate it.
  void serverResponse;
  return false;
}
