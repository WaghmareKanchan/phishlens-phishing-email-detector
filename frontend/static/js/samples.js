/* Demo e-mails for the sample buttons (taken from the original UI). */
export const SAMPLES = {
  bank: { from:'HDFC Bank Security <alerts@hdfcbank-secure-login.com>', subject:'URGENT: Your account will be suspended within 24 hours',
    body:'Dear Customer,\n\nWe detected unusual activity on your account. You must verify your password and confirm your card number immediately or your account will be suspended.\n\nLog in now: http://hdfc-verify.secure-login.xyz/update?id=88421\n\nThis is a final notice.\n\nHDFC Security Team' },
  prize: { from:'Global Rewards <winner@lucky-draw-claims.top>', subject:'Congratulations!!! You won a $1,000 gift card',
    body:'Dear User,\n\nYou are the lucky winner of our monthly lottery. Claim your free prize before it expires. Act now, this is your last chance!\n\nClaim here: https://bit.ly/3xPrize99\n\nTo release the reward we only need your login details.' },
  parcel: { from:'Amazon Delivery <track@parcel-notify.top>', subject:'Your parcel could not be delivered',
    body:'Hello,\n\nWe tried to deliver your package today. Please confirm your address and pay the small redelivery fee immediately.\n\nhttp://185.203.116.24/track/redeliver\n\nIf you do not respond within 24 hours the parcel will be returned.' },
  real: { from:'Priya Nair <priya.nair@college.edu>', subject:'Project review moved to Thursday',
    body:'Hi team,\n\nThe project review has moved to Thursday at 3 pm in Room 204. Please bring the latest version of your report.\n\nThe agenda is in the shared folder, so no need to email me your slides beforehand.\n\nThanks,\nPriya' }
};
