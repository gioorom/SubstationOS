"""
The Shared Kernel: the small set of concepts more than one bounded
context legitimately shares.

Membership here is deliberately hard to earn. A concept belongs in the
Shared Kernel only when duplicating it would create two definitions of
the *same* idea that could silently drift apart, and when no single
context can reasonably be said to own it. Pagination qualifies: "which
slice of a list did you ask for, and what came back" means exactly the
same thing to Projects and to Documents, and neither owns it.

Nothing engineering-specific may live here. A concept that means
something slightly different to each context is not shared - it is two
concepts, and each context should declare its own.
"""
