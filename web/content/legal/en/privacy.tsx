import { CONTACT_EMAIL, SITE_NAME } from "../../../site.config.ts";

export default function Privacy() {
  return (
    <article>
      <h2>Who is responsible</h2>
      <p>
        The controller for this site is {SITE_NAME}. Contact: {CONTACT_EMAIL}.
      </p>
      <h2>What we collect</h2>
      <p>
        This site does not itself collect personal data from its visitors. The site has no accounts,
        no forms, no newsletter, no comments and no analytics.
      </p>
      <h2>Hosting and access logs</h2>
      <p>
        The site is served as static files by a hosting provider based in the United States
        (Netlify). To run and secure its service, the provider keeps technical access logs, such as
        IP addresses, browser details and request times. These logs can be personal data. We do not
        use them for anything other than operating and securing the site. The provider may process
        them outside your country, including in the United States, and keeps them for the period set
        by its own policy. Our basis is our legitimate interest in operating the site.
      </p>
      <h2>News processing</h2>
      <p>
        To prepare our pre-match analysis we store the headlines and links of publicly available
        football news. Headlines can mention player injuries. They are sent for analysis to a
        third-party artificial intelligence service (TypeSafe), which may process them outside your
        country. We publish no player health, injury or other player-level information on this site;
        the analysis is turned into team-level numbers only.
      </p>
      <h2>Referee names</h2>
      <p>
        For Türkiye's Süper Lig matches we show the name of the head referee appointed by the
        Turkish Football Federation (TFF), with that source, only once the TFF has announced it. We
        collect this name from the TFF's public appointment pages.
      </p>
      <h2>Local storage</h2>
      <p>
        Your browser stores a single entry recording that you confirmed you are 18 or older. It
        never leaves your device.
      </p>
      <h2>Your rights</h2>
      <p>
        Depending on where you live, data protection law (such as the UK GDPR, the EU GDPR or
        Türkiye's KVKK) gives you rights to access, correct and erase personal data about you and to
        object to its use. Send requests to {CONTACT_EMAIL}. You can also complain to your data
        protection authority; in the United Kingdom this is the Information Commissioner's Office
        (ICO).
      </p>
    </article>
  );
}
