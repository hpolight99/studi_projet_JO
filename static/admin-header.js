// Liste des liens du menu admin (ici en JS direct)
const headerHtml = `
<header class="wrap">
  <div class="nav admin-nav">
    <a href="/">🏅 JO France</a>
    <a href="/admin">Admin</a>
    <a href="/admin/orders?status=paid">Billeterie</a>
    <a href="/admin/users/list">Utilisateurs</a>
  </div>
</header>
`;

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("global-admin-header");
  if (container) {
    container.innerHTML = headerHtml;
  }
});
