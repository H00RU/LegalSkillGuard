% Text
% Alice has paid wages of $3200 to Bob for domestic service done in her home from Feb 1st, 2017 to Sep 2nd, 2017, in Baltimore, Maryland, USA.

% Question
% Section 3306(c)(2) applies to Alice employing Bob for the year 2017. Contradiction

% Facts
:- discontiguous s3306_b/8.
:- [statutes/prolog/init].
service_("domestic service").
patient_("domestic service","Alice").
agent_("domestic service","Bob").
start_("domestic service","2017-02-01").
end_("domestic service","2017-09-02").
location_("domestic service","Baltimore").
location_("domestic service","Maryland").
location_("domestic service","USA").
purpose_("domestic service","domestic service").
location_("domestic service","her home").
payment_("paid").
agent_("paid","Alice").
patient_("paid","Bob").
start_("paid","2017-09-02").
purpose_("paid","domestic service").
amount_("paid",3200).
s3306_b(3200,"paid","domestic service","Alice","Bob","Alice","Bob",_).

% Test
:- \+ s3306_c_2("domestic service",_,2017).
:- halt.
