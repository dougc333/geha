# Serval School transcripts

All sessions in one file, in course order. 201 Databases is not included (no transcript yet).

- [Serval 101 - ITSM Basics](#serval-101---itsm-basics)
- [Serval 102 - Automations](#serval-102---automations)
- [Serval 103 - Access Management](#serval-103---access-management)
- [Serval 104 - Knowledge, Analytics, & Campaigns](#serval-104---knowledge-analytics--campaigns)
- [Serval 105 - Governance, Permissions, & Teams](#serval-105---governance-permissions--teams)
- [Serval 202 - Journeys](#serval-202---journeys)
- [Serval 203 - Core ITIL Practices in Serval](#serval-203---core-itil-practices-in-serval)


---

# Serval 101 - ITSM Basics

Transcript from the Zoom Events recording, speaker and timestamp per turn.

**Davison Chung** [00:00:19]

On the next slide here, where we're at in our Serval School.

**Davison Chung** [00:00:23]

Progress.

**Davison Chung** [00:00:27]

Great, yeah, so we're… this is the first session of our Serval School program. This is also the first session of our Foundations 100 series program, which covers all the foundational and basics. We also have an advanced series, and taking all of those classes, or attending all of those webinars will make you eligible to take our Serval Certified exam, and mean that you are a true Serval Pro. And so, with that, I'm going to hand it

**Davison Chung** [00:00:51]

Jackson, who can get us started on the content.

**Jackson Schorer** [00:00:57]

Thank you very much, Davison, and hello everyone. I'm excited to be talking about the ITSM Basics today. Of course, it's the kind of initiator session for this 100 series, so I'm glad that you're all joining us today. My primary focus, as mentioned, will be ITSM Basics, and I will be talking about a number of different components

**Jackson Schorer** [00:01:19]

That go along with this system, the kind of fundamental settings components that enable us to make the ticketing feature very configurable.

**Jackson Schorer** [00:01:28]

how that works off of the core model that we provide at Serval, as well as a number of specific components and features that really make this more robust. On top of that, I'll be giving a generalized intro to Serval, and getting into a little bit more detail here, I will be talking about things like tags, categories, and how those contribute to assignment and routing. I'm talking about SLAs, the priority and status

**Jackson Schorer** [00:01:53]

attributes, and these are both kind of things that can be applied with the inference model, along with categories and tags, and that's something that I will highlight in much greater detail as part of this presentation, as well as kind of

**Jackson Schorer** [00:02:07]

Working and navigating tickets as an agent, builder, etc, and many more things.

**Jackson Schorer** [00:02:14]

Now, taking a step back and thinking about Serval,

**Jackson Schorer** [00:02:19]

The essence of Serval is an AI-native platform, and what that means is that we have built this platform very conscientiously with regard to weaving in the AI components into the system. And so we have a dual agent system here. We have a help desk agent and an automation agent, and the help desk agent is what is ultimately user-facing.

**Jackson Schorer** [00:02:42]

It is what makes all of those interactions for your end users, not only kind of integrate with the system that we've built, insofar as it can use the tooling and other systems that we've built.

**Jackson Schorer** [00:02:53]

But it is also able to adapt and respond more probabilistically. So different types of questions, Serval can reason to get the information it needs to provide the most accurate answer, or initiate any of the tooling that it has at its disposal. And that automation agent, called Catalyst in Serval, is what empowers your builders, your operators in Serval to construct the automation

**Jackson Schorer** [00:03:18]

and the tooling necessary to enable the help desk to better help your end users. And given that the automation agent can work from plain language prompts, it's very easy to build and get the ball rolling when you start creating automation in Serval and those automations results or those prompts to create automation result in TypeScript. So is therefore

**Jackson Schorer** [00:03:43]

a creation event to build out, deterministic actions. And there are many other components of the automation layer here, which I will reserve for the future conversation in that follow-up webinar.

**Jackson Schorer** [00:03:58]

Now, of course, aside from this dual-agent structure, which both work together in tandem, and also with which are involved the kind of inference model.

**Jackson Schorer** [00:04:07]

We also have access management, and we can think about this insofar as we integrate with an IDP and can enable SCIM provisioning via JIT, or we can also do direct integrations. And so there's a number of ways where Serval can very easily regulate and control as well as initiate access management and then provide that high-level auditability on those actions in the system.

**Jackson Schorer** [00:04:31]

with an increasingly more robust governance model.

**Jackson Schorer** [00:04:35]

Lastly, we have…

**Jackson Schorer** [00:04:37]

a great amount of support with regards to HAM, SAM, and CMDB. We have the ability to create

**Jackson Schorer** [00:04:45]

essentially enumerate database tables that can pull information from various sources. You can think about an ingestion workflow that's pulling key information about your computers, your hardware, from your MDM, the ability to view a significant amount of information in context with itself, or cross-context with other information in data tables, and of course, ingest

**Jackson Schorer** [00:05:10]

information from your IDP for user information. And that's something that we will actually talk about or at least reference in today's session, less so in terms of how the ingestion works, but more so in terms of when that ingestion is coming in, how are you leveraging the information that you're collecting about users in the context of ticketing?

**Jackson Schorer** [00:05:30]

And so, of course, given that today's session is focused on ticketing, it's important to think about the initiator for these tickets, or the creation event that builds these tickets in Serval. And certainly, within our web app, these tickets can be created on request, right? Each high-level request will create a ticket.

**Jackson Schorer** [00:05:50]

Or depending on your setup, maybe more than one ticket with some kind of tasks and dependencies.

**Jackson Schorer** [00:05:56]

But of course, given that we integrate with various other platforms, Slack.

**Jackson Schorer** [00:06:01]

Teams, email, and building out more robust information around phone as well. All of these channels to entry into Serval enable us to create tickets and track tickets from these sources, and we will look at a number of that in just a moment here.

**Jackson Schorer** [00:06:19]

But of course, as I was mentioning previously, this inference model versus the help desk agent. And the help desk agent is something I'll defer in a little bit more detail, but…

**Jackson Schorer** [00:06:30]

all of our agents, or most importantly, our help desk agent, employs the inference model, and that's something that enables Serval to take a lot of passive actions, or to act on tickets and change and update information, rather than having some operator do so.

**Jackson Schorer** [00:06:47]

And of course, given that we have this kind of native model, we have all of the fundamentals around that in terms of setting up how you categorize tickets, how tickets are assigned to your operators in the system, and of course, how you're tracking the completion of those tickets across SLA, priority, or other types of information.

**Jackson Schorer** [00:07:08]

Lastly, as I mentioned.

**Jackson Schorer** [00:07:11]

Today's primary focus will be that inference model, though there will be a more explicit discussion about the help desk agent, and of course, the automation agent in later sessions. And we will be looking directly at how the inference model applies. So I'm actually going to jump right into Serval here, and we can take a look.

**Jackson Schorer** [00:07:34]

So, as you can see, we've entered into a team here in Serval. This is a kind of a fictive IT team, let's say it's the IT team for a company.

**Jackson Schorer** [00:07:45]

Now, what you'll see right away is I'm entering into this new request feature, and this is, as I mentioned, a primary entrance point into Circle. And right off the bat, one thing I want to highlight is this auto-select team component.

**Jackson Schorer** [00:07:58]

This is the first example.

**Jackson Schorer** [00:08:01]

showing the inference model at play. Depending on the type of request that I input in this input box, Serval has the ability to route that message to the appropriate team based on a number of factors. So the inference model has information about each team or each workspace that you have within Serval.

**Jackson Schorer** [00:08:21]

Now, you might have to start out an IT team. Maybe then you have a security team. Maybe you then have a people or an HR team, et cetera. And you start adding teams.

**Jackson Schorer** [00:08:33]

And now, certainly, you might also have sandbox, or kind of these working teams. I want to be clear that you can control directly whether or not a team is viewable by the inference models. You could have 10 teams, but only 5 of which are viewable for this auto-routing.

**Jackson Schorer** [00:08:51]

So you have direct control over whether or not a team is even discoverable by auto-routing, and Serval's reasoning or logic behind auto-routing is actually comprised of a number of things. It's not simply just

**Jackson Schorer** [00:09:06]

how you define that team. It's actually the contents of that team itself, and so what you'll find is, as you're building organically within a team, as you build skills, as you build workflows, as you create knowledge, and certainly as you define the actual description of that team.

**Jackson Schorer** [00:09:23]

All of these factors contribute to how that team is understood by Serval, and so organically, what you'll end up doing is creating a very robust definition for how Serval can route to the correct team.

**Jackson Schorer** [00:09:36]

And certainly, there will be innumerate teams selectable. In this case, I have many more than just a couple teams. But if I were to input a response here, I suspect it would likely land on a different demo team that has much more robust answers on the IT fundamentals. But the auto-select is just kind of one component. Certainly, I can navigate to my own team and create a request directly here, and I know that

**Jackson Schorer** [00:10:01]

This ticket will land on this team.

**Jackson Schorer** [00:10:04]

Now, speaking of tickets landing on a specified or desired team, I'm going to take a little bit of time here and look at Slack. So I'm just going to pull over some space here, and I'm going to bring in Slack, to this to demonstrate a couple of things. So my goal here is to demonstrate.

**Jackson Schorer** [00:10:23]

essentially how these high-level requests in Slack arrive in Serval. And I'll actually be showing them side by side so that we can see, kind of both

**Jackson Schorer** [00:10:33]

In presence of one another.

**Jackson Schorer** [00:10:38]

So let's say I would just put in a couple high-level requests here. Something like…

**Jackson Schorer** [00:10:43]

what's the Wi-Fi password, or maybe I have a visitor coming, and I want to have a, a guest Wi-Fi code for a visitor coming Thursday, or maybe I want to have, perhaps my Zoom call has been cutting off At 40 minutes, or…

**Jackson Schorer** [00:11:02]

maybe I need a higher tier license or something like that, hypothetically. Something like, my Zoom policy counter for 40 minutes, can I get a pro license? No, you can see, immediately what starts happening is

**Jackson Schorer** [00:11:15]

There are indicators of Serval's response, as well as indicators of some kind of decision.

**Jackson Schorer** [00:11:23]

And if we look to our right, we can see that these responses, upon reply, are also creating tickets simultaneously. So 24, 25, and 26 were all created just this instant.

**Jackson Schorer** [00:11:34]

Basically, immediately after inputting these initial messages. And if we open two side-by-side here, so if we open this Wi-Fi request.

**Jackson Schorer** [00:11:43]

Let's close this so we can view it better.

**Jackson Schorer** [00:11:46]

and we open the Slack thread, we can see that both are basically representing the same information, certainly structured differently, unique to the platform. But a couple of things that I want to call out here. So you'll notice that a couple things happened right away.

**Jackson Schorer** [00:12:03]

On creation of the ticket, or should I say, on the initial send of this message in Slack.

**Jackson Schorer** [00:12:09]

A message was threaded from this originator into Serval.

**Jackson Schorer** [00:12:15]

And you'll see that Serval updated the request name to Wi-Fi password request. So, based on the contents.

**Jackson Schorer** [00:12:22]

of this message, it automatically created this title, and this title is another kind of application of this inference model, insofar as, depending on what type of information you put, a summative title will be created. Now, because we have a knowledge base connected.

**Jackson Schorer** [00:12:39]

Which is something that will be covered in more detail, but essentially, if you have a knowledge base, either integrated with an external source like Notion, Confluence, etc, or you build one natively in Serval, Serval will be able to leverage the information dynamically to answer questions. Now, I provided a very general question.

**Jackson Schorer** [00:12:59]

Which has a very clear answer. And so if that answer is contained in my knowledge base, Serval can answer it very easily.

**Jackson Schorer** [00:13:06]

There is no shared Wi-Fi password in this instance.

**Jackson Schorer** [00:13:10]

But it was able to give me some information about it nonetheless.

**Jackson Schorer** [00:13:14]

And you can see that Serval has marked this request as done. So this is another application of the inference model, wherein Serval made a determination that, based on the information it provided, it could mark this status here as done.

**Jackson Schorer** [00:13:30]

Inferring that, yes, this is what I wanted. Now, certainly this is not binding.

**Jackson Schorer** [00:13:35]

I could say something like, Actually, this is not working…

**Jackson Schorer** [00:13:42]

Oops. Well, no need to yell.

**Jackson Schorer** [00:13:47]

Working for me, something like…

**Jackson Schorer** [00:13:57]

Now…

**Jackson Schorer** [00:14:02]

some kind of follow-up response, and I wanted to open both of these at the same time so that we can see how messages in one channel thread to the other.

**Jackson Schorer** [00:14:12]

And you can see that Serval is attempting to understand if it can, kind of reply based on the information. You can see that the message arrived on both sides, and this highlights something important here, which is the concept of

**Jackson Schorer** [00:14:26]

Threading. So if I respond in this Slack thread, or in this ticket thread, in any case, the answer will be sent back.

**Jackson Schorer** [00:14:36]

So now that it has been assigned, maybe there's something noted, we will… Okay, into this.

**Jackson Schorer** [00:14:47]

And you can see that as I post this message here.

**Jackson Schorer** [00:14:49]

it will arrive back in this thread via Serval. So in this case, Serval is posting the message, but of course it is still me as the operator in both cases. And you'll find that for some of your end users, they might operate almost exclusively

**Jackson Schorer** [00:15:05]

in Slack, and may never need to actually enter into Serval, because so many of these processes are actually being either handled by Serval, or your agents are acting in Serval, but don't need to go into Slack, or vice versa. It's kind of very easy to jump between the two.

**Jackson Schorer** [00:15:21]

And a couple other things I wanted to call out here as an initial preview, and we'll actually circle back to them with greater detail in just a minute here.

**Jackson Schorer** [00:15:30]

But as you can see, a number of things happened when I provided that follow-up request. Most importantly, you can see that it is now set to in progress. And so, essentially, my

**Jackson Schorer** [00:15:43]

response indicated that I needed more information, and I also indicated urgency. I said, hey, this is not working for me, I really need to connect now. What should I do? So I'm indicating to Serval

**Jackson Schorer** [00:15:55]

urgency in the nature of my response, and you'll notice that Serval actually interpreted that by updating the priority to high, because I'm indicating, hey, I need this right now. And I certainly could have provided more context, but that's enough for Serval to apply this property change.

**Jackson Schorer** [00:16:12]

via the inference model, which is another thing that I was mentioning previously as falling under that inference umbrella.

**Jackson Schorer** [00:16:19]

There's a number of other things that happened here in terms of leveraging.

**Jackson Schorer** [00:16:24]

an assignment group, assignment rules, a category, and we'll talk about all of those in just a minute, so I'm going to put a pin in that, but all of these are also applications of the inference model, applying attributes, and those attributes being leveraged to trigger other systems.

**Davison Chung** [00:16:40]

Hey, Jackson?

**Davison Chung** [00:16:43]

Can you talk a little bit about how the inference model works in tandem or separately from, like, skills that you might set for the help desk agent?

**Jackson Schorer** [00:16:51]

Absolutely.

**Jackson Schorer** [00:16:53]

So you can think about the inference model as kind of a base.

**Jackson Schorer** [00:16:57]

mostly always-on layer. What I mean by mostly always-on is

**Jackson Schorer** [00:17:01]

the inference layer, in many cases, is toggleable by attribute, so you could go to a status, for example, if we, kind of move Slack to the side here. If we look at any of these attributes that we're describing, right, so…

**Jackson Schorer** [00:17:18]

something like a status within a ticket type. You can see that any of these are selectable by AI, which means that we can toggle whether or not they are applicable or can be applied by Serval as part of inference.

**Jackson Schorer** [00:17:30]

And there's a similar logic to skills, where you can dictate a context in which a skill applies, or set a skill to always on in your settings. But I think the difference is

**Jackson Schorer** [00:17:41]

These… the status inference is something that is immediately applicable across many attributes over all ticketing.

**Jackson Schorer** [00:17:48]

Whereas skills are something that you will custom craft yourself, and certainly both are customizable, so I will caveat that statement. But skills are something that provide more nuance in terms of a number of things.

**Jackson Schorer** [00:18:01]

how Serval engages, you could think about creating a skill that changes the tone, or the way in which Serval responds to certain types of requests. You could create a skill that looks for certain information and responses, and when that information is provided, enforces the activation of a specific workflow.

**Jackson Schorer** [00:18:21]

There are many kind of different use cases like that, and there's certainly many more than I just described there, but skills are kind of, like, level 2.

**Jackson Schorer** [00:18:29]

If inference is the core system that makes things run more smoothly, skills are where you can really start making your space

**Jackson Schorer** [00:18:38]

directly catered for you and your team's purposes. And that's, I think, the key difference, is the skill piece gets much more robust and has many more controls, and are oftentimes reacting to certain things, or preserving a certain modus operandi at a higher level of abstraction on tickets.

**Jackson Schorer** [00:18:55]

Does that answer the question? I could certainly talk into more detail on anything there.

**Jackson Schorer** [00:19:08]

Well, I'll keep moving along then.

**Jackson Schorer** [00:19:11]

Umm.

**Jackson Schorer** [00:19:14]

And this is actually probably a great segue, given that I jumped into the status section here to talk a little bit about that, and I think I'll kind of continue… I think that's a very good question, because I think it's relevant to, how we think about a number of things here, right? Because I was talking about

**Jackson Schorer** [00:19:30]

things being customizable.

**Jackson Schorer** [00:19:32]

And certainly.

**Jackson Schorer** [00:19:34]

for things like status, right? The attributes that are applied by inference are also customizable themselves. Something that I mentioned previously was this concept of a team description feeding into the auto-routing model. And for most inference, application.

**Jackson Schorer** [00:19:50]

A label and a description, or a title and a description, are the kind of two components that make things inference applicable. So essentially, anything that has some kind of name, in this case, we have these status names, this description here is ultimately what enables Serval to

**Jackson Schorer** [00:20:08]

effectively apply these, just as how, if you created a skill, that description for the skill, or the context in which the skill applies, both inform Serval how to apply these, or when to apply these.

**Jackson Schorer** [00:20:20]

both, in all cases. And so certainly, you have these statuses that come out of the box. You have things like to-do, in progress, awaiting approval, done, and canceled. However, you can see here that I've added two custom, awaiting requester and action required, because these are kind of common use cases that I see, and these are also skills that… or, statuses, sorry, that I want to have available

**Jackson Schorer** [00:20:45]

for Serval to select, because I think they are relevant to other components, like SLA. To give you a specific example, this awaiting requester field is something that I would use as part of the SLA process when we start thinking about pause conditions for SLA, where if

**Jackson Schorer** [00:21:02]

me as an agent or operator, I've provided some kind of remediation for an end user, and I'm waiting… I'm awaiting confirmation that that remediation has succeeded, or maybe I asked for some kind of expanding information on their problems so that I could better provide support. In any of those cases, the ball's in their court, and if they take

**Jackson Schorer** [00:21:22]

a much longer period of time, we certainly don't want the SLA timer ticking down while I am awaiting that end user response. Hence the creation of the status, and hence why it being dynamically applied by Serval's inference is very effective for protecting your… the accuracy of your SLA, for example.

**Jackson Schorer** [00:21:41]

And you could think about many other use cases for this. To give you a kind of a interesting, tangible one that I've seen, I have a… one of my customers, we built a custom done status called Serval Done.

**Jackson Schorer** [00:21:55]

And they wanted to have more granularity thinking about when does Serval fully close a ticket end-to-end? And so we created this custom status in the done category.

**Jackson Schorer** [00:22:06]

And of course, you can kind of change the color, you can give it a different indicator so that it's more clear that it is distinct, but because they were kind of working around different.

**Jackson Schorer** [00:22:18]

fully AI-closed ticketing, and they wanted to see exactly when those are occurring, we built a custom status that Serval would apply when it would complete a ticket end-to-end with no human intervention.

**Jackson Schorer** [00:22:31]

Where they wanted other, kind of, more distinct done labels for other human interaction.

**Jackson Schorer** [00:22:36]

So you could get very specific and very much granular with these statuses, and certainly.

**Jackson Schorer** [00:22:43]

Stepping back here.

**Jackson Schorer** [00:22:45]

Okay.

**Jackson Schorer** [00:22:47]

This is not constrained, just to broad statuses, so each ticket type that we provide in Serval.

**Jackson Schorer** [00:22:54]

And there are a number of ticket types. So right now, we were looking at the primary, which is a request.

**Jackson Schorer** [00:23:04]

Excuse me. So any ticket coming in will primarily be this request type. That is the most common type, that is the main ticketing type.

**Jackson Schorer** [00:23:12]

And you can see here that, as I was mentioning previously, that auto-routing is only possible because I have this toggle selected.

**Jackson Schorer** [00:23:19]

And so, certainly, you would have this turned to hidden for any of your, kind of internal testing teams.

**Jackson Schorer** [00:23:26]

But any high-level request, so those messages that I was sending in Slack, or something that is sent via Slack DM to Serval, any of these entranceways into Serval will create a ticket and will predominantly be a request. However, depending on what I have applied, if I have an incident turned on, if I have

**Jackson Schorer** [00:23:45]

Change, problem, major incident.

**Jackson Schorer** [00:23:47]

Serval will correctly switch the ticketing type.

**Jackson Schorer** [00:23:52]

to that ticket upon arrival. And each of those ticketing types have, of course, their own statuses, and therefore their own status to be applied via inference.

**Jackson Schorer** [00:24:04]

And certainly, one other component that I want to mention here, or I should say two, are transitions and custom fields. Now, if I were to enable transitions here.

**Jackson Schorer** [00:24:15]

One thing that I can do is dictate from which statuses.

**Jackson Schorer** [00:24:21]

transition can occur. And so this lets you create a more strict model in terms of how a status goes from, or potentially from to-do to in progress to done.

**Jackson Schorer** [00:24:32]

Or backwards down that chain, because as you saw previously, there was an instance where I needed to take it to be reopened. And that's something that Serval can certainly hand dynamically at present, but maybe you have more strict controls around this process, and the transition model is what enables that.

**Jackson Schorer** [00:24:49]

And then lastly, custom fields. So you can add custom fields that provide some other type of information that are attached to tickets, and these can be applied by workflows, they can be applied by a number of components, you can apply them manually.

**Jackson Schorer** [00:25:07]

But they allow you to basically embed other descriptors or information into the ticket itself, and are something that provides more granularity for your, kind of, labeling operations.

**Jackson Schorer** [00:25:21]

Next up on the inference model is, of course, priorities. As we saw, that high priority was applied when I indicated that there was this urgency.

**Jackson Schorer** [00:25:30]

And these priorities become particularly relevant if you're thinking about them in the context of SLA, as they can certainly key off different SLA windows or pathways.

**Jackson Schorer** [00:25:41]

But again, this description, these are the kind of, essentially.

**Jackson Schorer** [00:25:47]

Created descriptions, but these descriptions can be modified or adjusted as per the specific constraints of your team.

**Jackson Schorer** [00:25:57]

Next up, so we talked a little bit about these, I think, and I think status and priority, right, those are the core fundamentals for any type of ticket.

**Jackson Schorer** [00:26:05]

But.

**Jackson Schorer** [00:26:06]

some tickets, as you'll see in this kind of Wi-Fi request here. Maybe we want more information about them because certain

**Jackson Schorer** [00:26:15]

topics of information are being discussed within the body of the ticket. And for these instances, and we'll look at this Zoom Pro license request, for example, we can see that there is a software and licenses category, as well as a Zoom label.

**Jackson Schorer** [00:26:31]

Now, both are appropriate, given the contents, right?

**Jackson Schorer** [00:26:34]

matter of discussion is Zoom, and this has to do with getting a specific license, hence the software and licenses category being applied. Now, what differentiates categories and labels is a couple of things. Categories, you can think about them as the highest value

**Jackson Schorer** [00:26:52]

summary of the contents of your ticket. So a category, there will only ever be one applied to a ticket. Now, you could certainly change the category, but what I mean by only ever one is there's only ever one at any given time.

**Jackson Schorer** [00:27:05]

And this category represents everything in the ticket body, and notably, categories are applied on escalation. So, as we saw in that ticket just now.

**Jackson Schorer** [00:27:17]

The ticket was… escalated by Serval.

**Jackson Schorer** [00:27:22]

So Serval looked at the response and determined that based on its available knowledge, or based on some kind of nature of importance.

**Jackson Schorer** [00:27:31]

it needed to escalate. And now, certainly, I could say, hey, can you escalate? And that would trigger this. But this escalation event, is basically a two-fold event. There is the escalation itself.

**Jackson Schorer** [00:27:43]

Kind of thinking about it as a logged action that something was escalating. And then oftentimes, depending on how you set up your system, the result of escalation is assignment.

**Jackson Schorer** [00:27:55]

And so, you'll see here that what happened was the, kind of.

**Jackson Schorer** [00:27:59]

ticket was escalated, and the category applied. And so, categorization applies within the escalation window, but notably before assignment. And that's why it matters that there's these two events that are part of escalation. Escalation.

**Jackson Schorer** [00:28:13]

And assignment, because what can happen is you have escalation, category application, assignment, and you can therefore use categories to be very explicit about how assignment functions within your team.

**Jackson Schorer** [00:28:26]

Because it will always apply before the assignment logic fires. But of course, it will only imply in these cases when escalation occurs.

**Jackson Schorer** [00:28:45]

And we can see that as a result of that assignment,

**Jackson Schorer** [00:28:49]

The routing rule brought it to a specific person, in this case, Camden, one of our agents on the team.

**Jackson Schorer** [00:28:55]

And a number of other components were updated, as well as this Zoom label. Now, we talked about categories a little bit, and just looking back at it, we can see that, again, without sounding overly redundant.

**Jackson Schorer** [00:29:09]

That software and licenses definition here.

**Jackson Schorer** [00:29:13]

was applied.

**Jackson Schorer** [00:29:14]

Or it was referenced in order for inference to apply this, this category.

**Jackson Schorer** [00:29:21]

We also saw that Zoom label applied. Once again, we see the AI auto-assign being toggled on here, or the ability to turn all of these on. Certainly, you can turn any… some of these, off.

**Jackson Schorer** [00:29:34]

etc. But… Labels are more enumerant.

**Jackson Schorer** [00:29:39]

You could have 10 labels applied to the same ticket, and they can apply in many contexts. You could apply them manually. They, of course, will be applied by inference.

**Jackson Schorer** [00:29:51]

Where applicable.

**Jackson Schorer** [00:29:52]

But…

**Jackson Schorer** [00:29:55]

Categories are better used for assignment, whereas labels can be used for understanding the contents of your tickets, especially if there's multiple, you can also use them

**Jackson Schorer** [00:30:05]

If your category is kind of your primary identifier of contents, maybe labels are used for, hey, this is a…

**Jackson Schorer** [00:30:12]

request about changing something within our system, or this is a request indicating something's not working correctly. You can also have them as kind of more operational labels for your team, things like that.

**Jackson Schorer** [00:30:26]

And… kind of…

**Jackson Schorer** [00:30:29]

We've talked about a number of things here, right? We've talked about status, priority, label, and category.

**Jackson Schorer** [00:30:36]

And so, stepping back and looking at the ticketing view here, all of these are certainly things upon which we can filter this information. This is just a generalized ticket view.

**Jackson Schorer** [00:30:47]

But I could go into my filter and filter maybe by status, something as simple as, I just want to see all of my in-progress tickets. Or maybe I want to see all of my in-progress tickets that are also

**Jackson Schorer** [00:31:00]

Related to Zoom.

**Jackson Schorer** [00:31:02]

And then I'll have a subset and a subset, right? And I can certainly keep adding labels here, or configuring the way in which this view is displayed for me. And if I were to go through and select a bunch of these different components here.

**Jackson Schorer** [00:31:17]

I could certainly save this view. Now, I'm going to clear this filter and show you some of the pre-saved ones, because there are certain ones that come

**Jackson Schorer** [00:31:26]

Pre-configured, and certain ones that you might want to create for the specific needs of your team or yourself.

**Jackson Schorer** [00:31:34]

involves me as a common one, or any ticket that, kind of has my touch on it. Now, in this instance, given that I am the requester for almost all of these tickets, this would probably be a less helpful, message, or a kind of

**Jackson Schorer** [00:31:48]

constraint.

**Jackson Schorer** [00:31:49]

However, maybe I only want to see ones that are assigned to me, and taking a step back, we can manage or manipulate the tickets here directly from this view. So I could take a bulk action of numerous tickets here.

**Jackson Schorer** [00:32:04]

And perhaps I would want to update the priority for all of them, or update the status for all of them.

**Jackson Schorer** [00:32:11]

That is certainly doable here. I could delete them, archive them, I could move these tickets to another team, and this is a callback to that assignment rule.

**Jackson Schorer** [00:32:19]

While assignment is very robust, maybe there's an instance where a ticket comes in, and it's nuanced. It is applicable to your team, but ought to also be managed by another team, and you ultimately, based on your discretion, decide, hey, actually, I think this ticket should go somewhere else. You can certainly move that ticket to another team.

**Jackson Schorer** [00:32:37]

As I'll show, right here. So you have a bunch of other options around tickets.

**Jackson Schorer** [00:32:43]

That are all just available within this menu in terms of, moving the ticket to another team, as you can see here, merging it with another ticket, linking. There's a number of actions that you can take to basically combine or reference tickets across one another.

**Jackson Schorer** [00:33:00]

to take a lot of the same actions that are available here, and a lot of the shortcuts are also present, so you can find… you might find that as you become more comfortable navigating tickets, that you can move through this much more efficiently.

**Jackson Schorer** [00:33:14]

But returning to this overall ticketing view, you can filter, you can dictate the layout.

**Jackson Schorer** [00:33:22]

And let's say…

**Jackson Schorer** [00:33:24]

there was this kind of Zoom label that I had mentioned previously. Maybe this is a view that I want, and maybe I want to assign this to myself here.

**Jackson Schorer** [00:33:32]

And in so doing, it will then now appear in my assigned list. So any modifications that I make here apply to the ticket directly, or at bulk, as I mentioned previously.

**Jackson Schorer** [00:33:47]

And you can see that I just assigned this ticket to myself, but we were also looking at an instance where tickets were being assigned automatically.

**Jackson Schorer** [00:33:54]

So let's take a look, actually, at the assignment rules behind this.

**Jackson Schorer** [00:33:57]

So we can see that Camden, one of our agents, and team members in IT Leads.

**Jackson Schorer** [00:34:04]

received that ticket. Now, part of the reason Camden received that ticket is because, or the main reason, I should say, is because the category

**Jackson Schorer** [00:34:13]

software and licenses is his purview. So within our team, he's the resident expert at these topics, and so I want to make sure that any tickets that come in, always assigned to him.

**Jackson Schorer** [00:34:23]

And you'll notice also that some of these tickets had both of these labels.

**Jackson Schorer** [00:34:29]

So the one that was assigned to Camden had the software and licenses category, as well as the Zoom label. So you might think, okay, well, how does Serve determine which to prioritize?

**Jackson Schorer** [00:34:39]

This assignment is hierarchical. So, essentially.

**Jackson Schorer** [00:34:44]

If… The, kind of…

**Jackson Schorer** [00:34:47]

assignment rule is listed above the other, in that case, Serval will then prioritize. So because this rule has been set as number one.

**Jackson Schorer** [00:34:56]

It will always prioritize this category to Camden over this Zoom label to Cole.

**Jackson Schorer** [00:35:02]

And so that lets you be very explicit about… around how these rules apply, because you can also understand that it will read through them, essentially, in order. And you can have more broad rules at the bottom.

**Jackson Schorer** [00:35:15]

Let's say, for example, we have some kind of schedule, and we have, maybe instead of just a generalized schedule like this for days of the week, we have some kind of schedule that is better dictated for

**Jackson Schorer** [00:35:29]

a specific person, so it's maybe it's Cole's schedule, or it's maybe Camden's schedule, or my schedule, and we have very specific non-overlapping hours.

**Jackson Schorer** [00:35:39]

It would be very possible to set those schedules, so if I were to add a new rule here.

**Jackson Schorer** [00:35:48]

I could set it based on a schedule.

**Jackson Schorer** [00:35:51]

And say, any ticket that comes in during the schedule assigns to Cole, for example.

**Jackson Schorer** [00:36:02]

And if that's the case, you can think about creating these groups essentially as catch-all groups that sit underneath your other assignment rules, which gives you more options in terms of to whom does something fall back within a window if it's not clearly defined with categories or labels or any of the other options, because certainly we can do these routing rules based on status.

**Jackson Schorer** [00:36:24]

Priority.

**Jackson Schorer** [00:36:25]

Category, ticket type, labels…

**Jackson Schorer** [00:36:28]

And requester field and a number of other things. And requester field is where, if you remember at the start of the presentation, I was talking a little bit about user attributes from the IDP, and having custom user fields. So it's possible in Serval to have a custom user fields table, that is sourced from your IDP. It will live on a

**Jackson Schorer** [00:36:48]

Specific team who enables this feature and can be shared with your other teams.

**Jackson Schorer** [00:36:52]

And enabling this feature allows you to be able to select information about that person from your IDP and use that as well. So, for example, maybe you have a, some kind of logic around

**Jackson Schorer** [00:37:07]

Through global operations, where different people, depending on their, kind of location, where they operate, on the requester front.

**Jackson Schorer** [00:37:17]

have some kind of label applied, or there's kind of some value in your IDP about their locale.

**Jackson Schorer** [00:37:23]

And you want to route specific requests to specific people on your team based on time zone or based on ownership. Maybe you have an expert who works with your EMEA team who's working in the US but handles a lot of the questions around that.

**Jackson Schorer** [00:37:37]

That's another example where you could apply that kind of built-in value associated with the requester themself.

**Jackson Schorer** [00:37:43]

To, route things effectively.

**Jackson Schorer** [00:37:47]

And then lastly, aside from kind of, these general rules, we have this fallback group here. So if we look at the settings, we can see that, we have essentially a round robin. So you could have round robin or human triage. Round robin will pick from amongst that group, and human triage, can just basically mean that you can select

**Jackson Schorer** [00:38:06]

For whom the task is given.

**Jackson Schorer** [00:38:09]

Now…

**Jackson Schorer** [00:38:12]

taking a step back from assignment, right? Once something is assigned to someone, now we are on an SLA clock, right?

**Jackson Schorer** [00:38:20]

And so it's, I think, an appropriate time to start thinking about SLA, to start talking about it a little bit in the context of everything to which I've alluded previously, right? The, kind of awaiting requester status coming back into play here. Now, I just have a general SLA policy here.

**Jackson Schorer** [00:38:36]

And this is probably less realistic insofar as.

**Jackson Schorer** [00:38:41]

I would suspect that you probably have one governed by priority.

**Jackson Schorer** [00:38:45]

But here we can see that we just have a very general.

**Jackson Schorer** [00:38:49]

Target time for resolution. Now, you'll see that there were two here. There is a time to resolution and time to first human response. Both can apply as separate SLAs.

**Jackson Schorer** [00:39:03]

And you'll also notice that I have something triggered here. Business hours. Now, we quickly paged over to that schedule and alluded to the concept of being able to set custom schedules, but.

**Jackson Schorer** [00:39:17]

Once you dictate those business hours, you can see I've selected this business hours schedule here.

**Jackson Schorer** [00:39:23]

And we can see the hours governed here. That means that SLA will only tick during the designated window. So if a request comes in right at the end of the day on Friday, 5 minutes to go, let's say it's, 4.55.

**Jackson Schorer** [00:39:37]

your SLA will take for exactly 5 minutes, and then continue for the remainder of those 4 hours that we've dictated Monday morning, assuming Monday is…

**Jackson Schorer** [00:39:46]

Business day.

**Jackson Schorer** [00:39:49]

And aside from dictating exactly when the clock is ticking.

**Jackson Schorer** [00:39:54]

Or for which specific schedules. You can also dictate criteria around, essentially when this SLA is attached. And this is where I was talking about priority, right? Where maybe I have this SLA policy should just be called high

**Jackson Schorer** [00:40:08]

Speed resolution, or urgent resolution.

**Jackson Schorer** [00:40:12]

And it's specifically for when the priority is something like, High and urgent.

**Jackson Schorer** [00:40:20]

etc.

**Jackson Schorer** [00:40:21]

Or perhaps, as I mentioned previously, we want to be able to pause the ticket when we are awaiting requester on the ticket, which seems fair, right? Again, that's something that we can apply dynamically. These are being applied by the inference model.

**Jackson Schorer** [00:40:37]

It's happening on your ticketing dynamically. Lastly, you can use workflows, workflows being the creator or created item from the automation agent.

**Jackson Schorer** [00:40:47]

And we could select a specific workflow and have some kind of action taken. So, for a common example of this would be some notification workflow that maybe

**Jackson Schorer** [00:40:57]

pings a Slack channel to say, hey, this SLA is going to breach in 30 minutes, make sure you complete this ticket.

**Jackson Schorer** [00:41:05]

Something like that.

**Jackson Schorer** [00:41:08]

Speaking of Slack channels, I just wanted to say one note really quickly on that. When you add Serval to a Slack channel, or any channel.

**Jackson Schorer** [00:41:16]

you… it's a very… the setup is essentially going into that pre-existing channel, if you have one, and at mentioning Serval to add the Serval agent, both.

**Jackson Schorer** [00:41:26]

generally to Slack, but also to your specific channel.

**Jackson Schorer** [00:41:31]

And once you accept that, because it'll provide a prompt to say, hey, this individual is not in your channel, would you like to add them? You say yes. You're then able to select and serve that channel.

**Jackson Schorer** [00:41:42]

Once that connection is made.

**Jackson Schorer** [00:41:44]

you can dictate how much Serval responds. You can have Serval set to always on, in terms of a help desk agent. You can have Serval set to.

**Jackson Schorer** [00:41:57]

When relevant, silent, on demand.

**Jackson Schorer** [00:42:00]

there's kind of a number of options here, but the reason I'm highlighting this is twofold. Number one, you have control over how the Serval Help Desk agent will engage and create tickets. And number two.

**Jackson Schorer** [00:42:15]

this is a direct link. So if I have one channel connected to this workspace, or maybe I have two, but those channels are only connected to this workspace.

**Jackson Schorer** [00:42:26]

That means the tickets created there will only ever land in this workspace. And so you can be confident that if you connect a channel directly to a workspace, those tickets will arrive at their intended destination.

**Jackson Schorer** [00:42:47]

Excuse me.

**Jackson Schorer** [00:42:48]

Continuing along here, we've talked a little bit about SLA, we've talked about assignment rules, we talked about how, kind of, to configure assignment rules and leverage the attributes that we have.

**Jackson Schorer** [00:42:59]

One final component that I want to highlight here is the CSAT side of things.

**Jackson Schorer** [00:43:05]

On tickets themselves, for your end users, you can enable feedback via our system, and not only will that be kind of dynamically applied to tickets.

**Jackson Schorer** [00:43:15]

In the right context, but it can also supply you with all of those results in a nice format from these tickets. So it's something you can simply toggle on or off, and you can dictate the frequency with which it's requested, for whom, or, yeah, for whom you're asking these questions.

**Jackson Schorer** [00:43:34]

And also dictate what constitutes a meaningful ticket for these responses. So, how many AI responses are we kind of setting as the minimum threshold for this application, or workflow runs? If you wanted something more

**Jackson Schorer** [00:43:50]

widespread, and you wanted it on every ticket, you could certainly set that as needed. You could dictate whether or not you want to include tickets that include human intervention.

**Jackson Schorer** [00:44:00]

As well as what kind of response feedback can be provided. Thumbs up, thumbs down, more binary, star rating, more qualitative, you can ask for comments.

**Jackson Schorer** [00:44:11]

etc.

**Jackson Schorer** [00:44:13]

And now, I will take a step back here, because we've talked about a number of components here, just to see if there's any questions. There's a couple other things that I can mention, as related to this, but I want to pause for questions, before I do.

**Davison Chung** [00:44:31]

Great.

**Davison Chung** [00:44:32]

Thanks, Jackson. Yeah, I want to open it up. Questions that anyone has, things that people are tackling, areas that people are interested in seeing. Maybe there's something that you, you know, like about whatever you're currently using, or a past ITSM.

**Davison Chung** [00:44:47]

that you want to understand whether… whether Circle has the… has the capabilities to replicate, or… or our own version of that, that would be a good time… that would be a good time to ask that as well.

**Davison Chung** [00:45:00]

But…

**Davison Chung** [00:45:01]

if no questions, or while people are typing or thinking of their questions, I'll just give a quick plug again for what we have going on for the rest of the week with Serval School. And so, you can find everything, at the website I just put in the chat, Serval.com slash Serval dash school.

**Davison Chung** [00:45:18]

We have our full 101 series this week. So 101 all the way through 105.

**Davison Chung** [00:45:25]

tomorrow will be our session on automations, which will go in depth on how to build workflows, how to build skills, how to build background agents, and use Catalyst, our automation agent. We also have two, sort of.

**Davison Chung** [00:45:39]

two non-foundational courses this week. Later today, we have a session that's focused on Serval for People Ops, so if you're on an HR or recruiting or other people ops team, where, you know, learn a little about the use cases and what modules are most, kind of, relevant for you. And then we also have a session on Thursday focused on journeys, which is our, kind of, cross-team.

**Davison Chung** [00:46:03]

Long process, management.

**Davison Chung** [00:46:06]

module. So, most frequently we see people using that for joiner, mover, lever, onboarding, offboarding, things like that.

**Davison Chung** [00:46:15]

There's a question about practice questions for the Serval test.

**Davison Chung** [00:46:18]

That's a good question. I do not… we do not have any practice questions right now, but maybe that is something that we can put together for you all. So, I will take that back to the team as something that we can provide. For now, in terms of if you are looking to get certified, as a reminder, you do have to attend, or view the.

**Davison Chung** [00:46:38]

full 8 courses in the 101 and 201 series. You can reach out to me, I'll put my email in the chat if you would like to reach out to me. Davison at Serval.com. If you have questions about the program, or the kind of process for getting, getting certified.

**Davison Chung** [00:46:57]

Yeah.

**Davison Chung** [00:46:59]

I do have a real question here. So, what is your recommendation for help desks that run on a 24-5 follow-the-sun type process when it comes to setting up SLAs and schedules? They have a number of different time zones involved in their help desk.

**Jackson Schorer** [00:47:14]

Absolutely. I think… so this is something that we do see quite a bit, especially with folks that have operations globally, or they maybe have someone that's based in London, they have someone that's based East Coast, West Coast, and the benefit of Serval System is you can kind of determine the best method for you and your team.

**Jackson Schorer** [00:47:34]

As I mentioned previously, you have the ability to build in these schedules, and so certainly, you could create schedules that

**Jackson Schorer** [00:47:43]

maybe even overlap with each other, assigned to specific people, specific teams, specific regions. You can certainly dictate the time zone of that region. But what you'll also find in Serval is a number of our features are

**Jackson Schorer** [00:47:56]

end-user location specific. So to give you a very, kind of tangible example of that, if I were to turn on something like requests or follow-ups, you can see that I can actually set, the component here to.

**Jackson Schorer** [00:48:12]

the requester's, time zone. And there's a number of other things like that for.

**Jackson Schorer** [00:48:19]

campaigns as well, where a message would arrive within someone's timing. So you have kind of different controls of that, but…

**Jackson Schorer** [00:48:27]

Stepping back at a more fundamental level, you can either dictate those different schedules

**Jackson Schorer** [00:48:34]

as separate schedules, because you can build as many schedules as you like, or you can use the automation layer to become kind of more specific, where let's say that rather than referencing those schedules, you just want to put some absolutes, right? Like, dividing the, kind of.

**Jackson Schorer** [00:48:51]

rotation of the sun, or the 24 hours of the day into multiple windows, and each of those windows is owned by a person, and you have a workflow that routes assignment.

**Jackson Schorer** [00:49:02]

according to that, that's something that you can also perform. So, ultimately.

**Jackson Schorer** [00:49:07]

there's… we have a bunch of the building blocks necessary to do this, and what it comes down to, what I've found with the teams with whom I work, is just kind of playing around with the best permutation of that.

**Davison Chung** [00:49:23]

Cool, great question.

**Davison Chung** [00:49:26]

All right, we have seven more minutes. Any other questions we can tackle while you have Jackson and I here?

**Davison Chung** [00:49:43]

Alright. Well…

**Davison Chung** [00:49:46]

How to get Serval certified. Okay, great, you know, great question. So process is relatively straightforward. Maybe if you want to show us the Jackson, if you can show the slideshow again quickly.

**Davison Chung** [00:49:59]

So, the process for getting Serval certified is pretty straightforward.

**Davison Chung** [00:50:03]

you need to attend the 8 webinars that are in our foundations and advanced courses. Once you've attended those, we'll reach out to you with, a link to a certification exam that you would be eligible to take. The exam is 50 questions, multiple choice, and you are allowed to retake it if you don't pass the first time, but once you've gone through the attendance of these webinars.

**Davison Chung** [00:50:28]

and pass the exam, you will be officially Serval certified, and you'll receive a certificate as well as a badge that you can share publicly and have for your records. And so that is the process. If you're having an issue with attending the webinar series live, we do highly recommend it for multiple reasons. One, because our product changes very rapidly, and so we want to make sure that you're getting the most up-to-date information, and then two.

**Davison Chung** [00:50:52]

So that you can interact and learn and get your questions answered in real time. We just find that that's a more, engaging and helps with people's retention of information.

**Davison Chung** [00:51:01]

If you're unable to make it for some reason to all of the sessions, or unable to complete, you can reach out to me at Davison at Serval.com, which is in the chat, and we can figure out an accommodation for doing the training asynchronously.

**Davison Chung** [00:51:15]

But yeah, that is the process. It is relatively straightforward. You can find these details also on our website, circle.com slash circle dash school.


---

# Serval 102 - Automations

Transcript from the Zoom Events recording, speaker and timestamp per turn. The recording text ends mid-sentence at 00:40:36.

**Davison Chung** [00:00:00]

Hi there, everyone. Happy Tuesday. Welcome to Serval 102, focused on Automations. I'm joined by Richard, who's on our Deployed Software Engineering team, and he's going to run you through all the content. I'm really excited to go over this session. It covers a lot of the really core features of Serval, from skills and workflows to catalysts and background agents.

**Davison Chung** [00:00:25]

And should really set you up to start building with Serval and automating work in Serval. And so, we want to make sure this is interactive, we want to make sure that you all are getting your questions answered. Please use the Q&A and the chat, liberally. If you have a more complicated question, you can always raise your hand as well, with that button at the bottom of the screen, and we can get to you live.

**Davison Chung** [00:00:47]

And so, yeah, hope to hear a lot of great questions, a lot of great engagement for you all, and with that, I'm going to hand it over to Richard.

**Richard Cheung** [00:00:53]

Awesome, thank you, Davison. I'm Richard, I'm one of the deployed engineers here at Serval, and super excited to be

**Richard Cheung** [00:01:02]

doing this Serval 102 session with you guys today, I think Automations is one of my personal favorites, because this is where you really start to see the power of Serval, see the power of how we've built workflows and skills.

**Richard Cheung** [00:01:15]

and how you guys can build these to configure your Serval instance and really start to see a lot of the, to really start to see a lot of the benefits of using Serval.

**Richard Cheung** [00:01:25]

So yeah, just as an overview, you know, we've got a few courses within our 100 series. Today, we're going to be focused on Automations. Our previous session was on the basics of Serval and ITSM in general, but a few other things to look out for are things about our access.

**Richard Cheung** [00:01:41]

about our knowledge, and about things around our governance and permissions. You'll also notice that we also have an advanced series, so we call this the Serval 200 series, and this goes over some more advanced concepts within Serval to hopefully get you guys set up there as well.

**Richard Cheung** [00:01:57]

Cool. Awesome, so let's dive straight into Automations. And so, as a quick overview of the agenda for today, I'm going to cover the differences between what we call workflows and skills.

**Richard Cheung** [00:02:09]

I'm going to cover what are the different types of workflows, and then we'll really get hands-on with what we call our catalyst agent. This is like our automation agent, and this is the agent you'll use to configure a lot of these, primitives and get your Serval instance up and running. And then we'll also tackle proactive or background agents.

**Richard Cheung** [00:02:29]

Which are really cool new features that are just agents that run on their own and go and do their own findings, come back with suggestions and reports for you. And so we'll go dive into all of that.

**Richard Cheung** [00:02:41]

Cool.

**Richard Cheung** [00:02:45]

So, throughout today's session, I want you guys to, remember this key principle, that Serval is really a platform of two agents, right?

**Richard Cheung** [00:02:56]

Last session, you guys saw the power of the help desk agent. This help desk agent uses the tools that your automation agent configures. Today's session will be focusing on this automation agent piece, which we also call Catalyst.

**Richard Cheung** [00:03:12]

And Catalyst is kind of this agent that knows about these Serval primitives, it knows about these, it knows how to set up your Serval, and it's the agent that you will talk to to actually set up these workflows and skills.

**Richard Cheung** [00:03:26]

And so let's go over another key principle here, which are that Automations are either what we call deterministic or probabilistic.

**Richard Cheung** [00:03:34]

Right? And so, an example of some automation that's deterministic are things like workflows. This means that every time you run it, it always produces the same result for the same input.

**Richard Cheung** [00:03:45]

Right, so you can think of this like a tool, right? It does one job or one action the same way every time, and then you will string together these different tools to really, to really get tasks done.

**Richard Cheung** [00:03:57]

The next thing are probabilistic, right? And so these are things like what we call our skills, and this is kind of like how our background agents also operate.

**Richard Cheung** [00:04:06]

Probabilistic things are kind of like a recipe, not a tool, right? Whereas tools are, you know, you do the same thing, it does the same thing every time you run it. Probabilistic is more like focus… is more like following a recipe.

**Richard Cheung** [00:04:19]

Where every time you run it, it might do something different, but you can really kind of use this as a tool to guide your help desk agent into doing the things that you want.

**Richard Cheung** [00:04:30]

Okay.

**Richard Cheung** [00:04:31]

And so, given these two, let's go over, kind of, like, the four automation types, or primitives within Serval, right? You'll see it kind of is, like.

**Richard Cheung** [00:04:41]

On the left, we kind of have, you know, these are the automation types that happen more on request. And on the right, these are the kind of things that happen more on their own. Right. So we kind of have this spectrum here.

**Richard Cheung** [00:04:52]

And so, starting from the left here, we have what we call workflows. These are our deterministic pieces of action.

**Richard Cheung** [00:04:59]

that we define for our agents, right? And so, these workflows can either be requested on their own, or they can be scheduled and extended, which we'll go over later in triggers. But at a high level, some examples of workflows might be things like resetting your password.

**Richard Cheung** [00:05:15]

It might be things like assigning devices to users. It might be things like, you know, it might be things like looking up a user record in an external system.

**Richard Cheung** [00:05:25]

or writing to a user record on an external system. So these are all, like, kind of, like, individual tools or actions that your agents can call, and that perform, basically, this kind of thing that is backed also in code. And so that's what workflows are in Serval.

**Richard Cheung** [00:05:43]

The next thing we have are what we call skills, right? So you can think of these kind of, like, recipe books or instruction manuals, and they really are, like, kind of like a document that tells your agent how to behave, right? Similarly to how you might have

**Richard Cheung** [00:05:57]

an instruction manual for a human user, or a human agent, right? These are… the skills are the way that you can hand off these instructions

**Richard Cheung** [00:06:06]

to, to your AI agent. And so some examples of skills are, like, for example, teaching your agent how to triage laptop issues, right? Maybe there's some predetermined kind of steps that you want the agent to generally follow. You could also teach it things like.

**Richard Cheung** [00:06:22]

you know, how you check and submit PTO, right? And so you can…

**Richard Cheung** [00:06:26]

Put into your skill, like, things about your PTO policy and things that you want the agent to note.

**Richard Cheung** [00:06:31]

So that's what skills are.

**Richard Cheung** [00:06:33]

And the next thing are triggers, right? And triggers are really the kind of extension of workflows. And so, what this means is that you can trigger workflows based on different things, based on different either events that happen within Serval.

**Richard Cheung** [00:06:46]

events that happen outside of Serval, through an external webhook, or even just on the schedule, right? So maybe, you know, if, for example.

**Richard Cheung** [00:06:54]

a user gets deactivated, in Workday, you want that to trigger a workflow in Serval, and that's something you do with a trigger. Another thing that you could do is also, like, scheduling PTO delegation, for example.

**Richard Cheung** [00:07:07]

We'll also dive into some other examples of triggers that you'll see within our platform.

**Richard Cheung** [00:07:12]

And on the very right, we have what we call background agents, or our proactive agents. These are agents that can go and run on their own, investigate issues, provide you reports, can even give you suggestions on workflows or skills that you should add to your Serval instance.

**Richard Cheung** [00:07:28]

In order to… based on the data that it sees, and based on, kind of, like, the interactions that your users have with Serval. And so, really, this opens up a world of all kinds of possibilities, right?

**Richard Cheung** [00:07:40]

A few that we've seen are, for example, finding anomalies within your Serval instance or within your tickets, right? We can do things like, you know, discovering recurring issues that happen again and again.

**Richard Cheung** [00:07:51]

Right? And letting our background agents suggest, hey, maybe we want to build a workflow. Maybe we want to build a skill for this. And then, of course, you can also do things like suggesting what licenses to reclaim. So, taking a look at your unused licenses, right?

**Richard Cheung** [00:08:05]

You can take a look at your external systems, you know, find out what licenses are not used, and figure out what you can reclaim to save your organization some money as well.

**Richard Cheung** [00:08:14]

So these are kind of, like, the four automation types in Serval, and kind of the primitives.

**Richard Cheung** [00:08:20]

Yeah, we'd love to dive into the platform and demonstrate these, but before we continue, Davison, any… Any questions from the audience?

**Davison Chung** [00:08:31]

No questions yet, but if you want to put in the chat anything that you'd like Richard to show.

**Davison Chung** [00:08:38]

in the platform, anything that we'd want to build, anything you're thinking about automating that you want to see how we might approach, we're happy to customize this portion and build some things, that you all are interested in specific. So, with that, I'll let Richard get us into the platform.

**Richard Cheung** [00:08:58]

Awesome, let's dive straight in.

**Richard Cheung** [00:09:02]

Cool.

**Richard Cheung** [00:09:04]

So this, in Serval, this is Catalyst, right? And you can get to Catalyst if you come into Serval, right? You'll see this big button here, Catalyst. This is going to be your entry point to a lot of what we're doing today, and a lot of how you configure Serval.

**Richard Cheung** [00:09:19]

will be done through Catalyst. Now, as mentioned, Catalyst is our automation agent that really understands the different primitives in Serval, and you will use Catalyst to set up workflows, skills, but also, you know, different things further down the line, like your access, your integrations, your knowledge sources.

**Richard Cheung** [00:09:37]

knowledge bases. Things like that we all do through Catalyst, and so, you know, this session's a great introduction to also using Catalyst.

**Richard Cheung** [00:09:45]

So let's dive straight in. Let's, let's first build a workflow together. So, really, all you need to do in Catalyst is just describe to it in natural language. So let's say I want it to…

**Richard Cheung** [00:09:57]

Build me a password reset workflow.

**Richard Cheung** [00:10:01]

or Octo.

**Richard Cheung** [00:10:03]

Right.

**Richard Cheung** [00:10:04]

ignore duplicates.

**Richard Cheung** [00:10:06]

And so I'll just send this out. You'll notice that, you know, I'm just…

**Richard Cheung** [00:10:09]

describing what I really want in just one sentence, right? Just a password reset workflow. And Serval has the knowledge to kind of go through, you know, the Okta documentation, understand how you can build the workflow for Okta. You'll also notice that I had to put here ignore duplicates, right?

**Richard Cheung** [00:10:26]

I have to do this because, you know, this is kind of like our demo environment, and we have this workflow set up already, and Catalyst is smart enough to know, hey, you've built this workflow before, you've built these things before, let's not build any duplicates, so I just needed to put it there.

**Richard Cheung** [00:10:41]

Another thing that I want to call out is you also notice Catalyst asking you questions, right? So in this case, it's asking me that I have two connections. Let's just pick the first one.

**Richard Cheung** [00:10:50]

And so, you know, Catalyst is not just kind of going out there and, you know, trying to do its own thing. It really is, you know, clarifying some questions with you, and kind of going through, going through that process with you and guiding you through it.

**Richard Cheung** [00:11:04]

So while that spins… oh, wow, that was quick.

**Richard Cheung** [00:11:08]

But you can see here that after it spins, right?

**Richard Cheung** [00:11:12]

You'll notice this panel on the right has popped up.

**Richard Cheung** [00:11:15]

This is kind of like our workflow preview panel, or the workflow detail panel. And what you'll see here is

**Richard Cheung** [00:11:22]

really the steps that your workflow will take, right? And so, you can see here that, okay, it's gonna… it's telling me that it's gonna first find the employee in Okta, and then it's gonna send me the password reset email. So you can see these steps here.

**Richard Cheung** [00:11:34]

Another thing that I'll call out is that you can also see the actual code.

**Richard Cheung** [00:11:38]

that, that Catalyst wrote for this, right? And so, really what workflows are at Serval are pieces of code that will run, whenever the workflow runs.

**Richard Cheung** [00:11:50]

You know, this is useful, but honestly, most of the time, we're just viewing… you know, we're viewing just the.

**Richard Cheung** [00:11:55]

Reviewing just the steps, because that's much easier.

**Richard Cheung** [00:11:58]

A few other things to call out here are that you'll notice this button here, add approvers, right? Because within workflows, you can have approvers that must approve before running the workflow. So, you know, given that this is kind of like maybe a sensitive thing, right, resetting passwords.

**Richard Cheung** [00:12:14]

So maybe I really want to add like an approver, right? So I can set like an approval procedure here, right? If I have some predefined ones, but can also create some procedures.

**Richard Cheung** [00:12:25]

Right? And what I can do here is I can add, you know, I can add either certain users that must approve.

**Richard Cheung** [00:12:32]

I can add certain groups that should approve.

**Richard Cheung** [00:12:35]

And for more complex use cases, I can even have a workflow that returns me, or that gives me the list of users that should approve.

**Richard Cheung** [00:12:44]

Right, and so you can really use this kind of, like, approval, you can really use this approval panel to really flexibly define, who should approve before you run certain workflows.

**Richard Cheung** [00:12:57]

And so this is kind of, like, the kind of how… what you can do to set up your workflow and kind of show… showcased how you use Catalyst to, set this workflow and the details that you can see from it.

**Richard Cheung** [00:13:08]

A few other things that I want to call out, right? Let's say, like, you know, you have a fresh Serval instance. You're really not… you're not too sure where to start.

**Richard Cheung** [00:13:16]

Right? We have, on our Serval side, configured a bunch of pre-installed workflows that you can add to your Serval instance. So, for example, here, if I click into my Okta, for example.

**Richard Cheung** [00:13:30]

Oh, sorry.

**Richard Cheung** [00:13:32]

I can see that these are the kind of, like, the predefined workflows that Serval has built that we've seen be helpful for a lot of our users, and you can actually click and add a lot of these, workflows.

**Richard Cheung** [00:13:45]

To basically do, like, kind of like a quick start for your Serval instance.

**Richard Cheung** [00:13:51]

So, another thing I want to call out here before we move on from workflows…

**Richard Cheung** [00:13:56]

is that, you know, if I go to a workflow where I've actually had a

**Richard Cheung** [00:14:00]

Had a bunch of,

**Richard Cheung** [00:14:02]

had a bunch of runs and had a bunch of versions here, is that you'll notice that we also have versioning for workflows. And so, you know, when you're writing workflows, you know, you have to explicitly publish them, and this creates, like, a new version of the workflow. And so, as you're updating workflows, as you're working with Catalyst, right?

**Richard Cheung** [00:14:19]

As you'll notice here, if we go back.

**Richard Cheung** [00:14:22]

Nothing gets published until… nothing gets published until we hit the publish button. So you'll see here that I'm still in the draft stage of this workflow.

**Richard Cheung** [00:14:32]

Now, I don't actually have the permissions to publish.

**Richard Cheung** [00:14:34]

Because I'm in the R demo instance, but, you know, in your instance, you'll be able to hit this publish button to then publish your workflow. And so this way, you can, like, iterate on the workflow, look at the steps, work with Catalyst without having to be like, hey, are my end users seeing these

**Richard Cheung** [00:14:49]

you know, updates as I'm working on it. No, you have to explicitly publish, and that's how we kind of do the… do the versioning and the auditing as well.

**Richard Cheung** [00:14:58]

And so, you know, obviously, this workflow I just created, I don't have any versions, I don't have any runs, so I can't showcase that to you. But here's an example of a workflow in which I have had a few versions and some runs.

**Richard Cheung** [00:15:09]

Right, so you'll notice here that I can view, kind of like my full version history, right? Can see when these different versions were published, and who published them, so if something went wrong, I can, you know, go back and, I can go back and see what happened.

**Richard Cheung** [00:15:24]

I can also compare the versions, and actually see the diff.

**Richard Cheung** [00:15:27]

Right? And so if I want to get even more granular and, like, see, hey, what exactly changed from this version to this version? I can then go ahead and see, see this in this panel.

**Richard Cheung** [00:15:39]

Another thing, too, that's pretty helpful as you're working with your workflows is this run history.

**Richard Cheung** [00:15:45]

Right, so I can see all the times that this workflow was run, I can kind of view the status of it, right? So, whether the workflow completed.

**Richard Cheung** [00:15:53]

In this case, it was canceled, right? And I can see, hey, this workflow's been running for quite some time, right? For 8 minutes. Maybe something's wrong with it, and I want to fix it. And obviously, if a workflow errors out, which I don't have in this example, but if a workflow fails to run, you can also see, kind of, the reason why it failed, and debug it that way.

**Richard Cheung** [00:16:12]

Right, another cool thing that I want to call out here is you can actually click Investigating Catalyst, and if I click that, you know, it actually just sends Catalyst the, the context for this run, and so I can hit that and ask Catalyst to then help me, like.

**Richard Cheung** [00:16:27]

fix up this workflow. And so you really start to kind of see the power of Catalyst and how it's able to not only set up these workflows for you, but also find out and fix, the workflows when things go wrong.

**Richard Cheung** [00:16:41]

Cool. And before we move on from workflows, another thing that I want to show you here is how you can view all your workflows in one page. So you'll notice here there's a button here, Workflows, right? And so when I come to this page.

**Richard Cheung** [00:16:54]

These are all the workflows that I have for my instance, right? I can organize them into folders. Of course, you can do that by clicking new folder, dragging things around, but Catalyst can also do this for you and organize your workflows into folders for you.

**Richard Cheung** [00:17:08]

And so, and I can do also, like, view it by… from different filters as well. And so you can really kind of get, like, a bird's eye view of all the different, workflows that you have.

**Richard Cheung** [00:17:19]

Cool. Any questions on workflows before we dive into skills?

**Davison Chung** [00:17:29]

No questions yet on workflows, but let's move over to skills.

**Richard Cheung** [00:17:34]

Awesome.

**Richard Cheung** [00:17:37]

Cool.

**Richard Cheung** [00:17:38]

So skills. Now, if you recall, if workflows were kind of like the actions or the tools that your help desk agent can use, skills are like the instruction manual.

**Richard Cheung** [00:17:49]

Right? And so you'll notice here, right, kind of similar view to workflows, but you notice this right-hand side panel for the skill looks a little different.

**Richard Cheung** [00:17:58]

We're not defining steps or pieces of code. Skills are really just instruction manuals or recipes, right?

**Richard Cheung** [00:18:05]

And so all we're telling Serval is, hey, two things. When should you use the skill? So when is the skill relevant? And what you should do when you encounter this situation.

**Richard Cheung** [00:18:17]

So…

**Richard Cheung** [00:18:19]

in this example, right, I have a skill that teaches Serval how I can triage and remediate laptop issues. And so, in this, when I should use this skill, right, it's telling me that… we're telling Serval, sorry, that, you know, whenever a user reports that their laptop's not working, and here are some examples of this, right, then we should use this skill.

**Richard Cheung** [00:18:42]

And then you'll notice here it's pretty detailed on, like, what exactly, Serval should do to try to fix

**Richard Cheung** [00:18:48]

someone's laptop, right? Because, you know, every organization has access to different, like, MDM policies, you know, different

**Richard Cheung** [00:18:56]

kinds of access into your users' laptops, and so it really is helpful to give Serval that context on what exactly it should do. Right, so you'll notice here we've defined some, like, high-level steps. First of all, like, find the device and diagnose it.

**Richard Cheung** [00:19:09]

Second, we triage on the health result.

**Richard Cheung** [00:19:12]

And then 3, maybe, like, when we want to escalate it to a human. And some cool things to call out here is that you'll notice that within the skill, we actually link to a bunch of different things, right? For example, we are telling Serval, hey, run this workflow, right, this laptop health check workflow.

**Richard Cheung** [00:19:29]

And then, or maybe even, like, reference another skill to use.

**Richard Cheung** [00:19:33]

Right? And so you can really like string together a lot of these workflows and skills together to really achieve something really powerful. Because in this case we're telling Serval, hey, use this skill first, right?

**Richard Cheung** [00:19:44]

And then when you triage it, you can run this skill for some, laptop remediation remotely. You know, maybe you want to run your laptop health check again.

**Richard Cheung** [00:19:54]

And then if, you know, if it really is that the laptop's broken, I can even surface a form.

**Richard Cheung** [00:20:01]

Right? That the user can fill out and request a new laptop.

**Richard Cheung** [00:20:04]

And so, really tagging all these different kind of Serval primitives and different things within Serval can really help us, you know, add a lot of power and intelligence to our help desk agent, and that's something that you can do with skills here.

**Richard Cheung** [00:20:20]

Other key things to call out within skills is that, again, right, skills are also versioned and audited, similar to workflows, right? So I can see, kind of, the versioning here, the diff.

**Richard Cheung** [00:20:33]

of what's changed, right? I can compare different versions.

**Richard Cheung** [00:20:38]

And again, right, if I was writing this skill from scratch, you know, it would say draft, right? I'm not just, like… it's not just, like, writing to the… it's not just writing and committing the skill, I have to do this explicitly by human as well. And this way, Catalyst isn't just, like, roguely writing skills, similar to workflows.

**Richard Cheung** [00:20:58]

Also, similar to workflows, you can see your kind of list of skills here, right? I can organize them into folders as well. I can see when it was last updated, the number of tickets that has used this skill, and so really you can, again, like, similar to workflows, see a bird's eye view of all the skills that you have.

**Richard Cheung** [00:21:16]

Another cool thing that I want to call out here, and this is actually available for workflows as well, but we didn't get into this just now, is you'll see this button called Suggestions.

**Richard Cheung** [00:21:25]

Right? And if you open this, these are actually suggestions for workflows and skills that, that Serval has identified of things that you should add.

**Richard Cheung** [00:21:36]

So, you know, for example, it's… in this case, it's suggesting me of this kind of remind owners of laptops workflow.

**Richard Cheung** [00:21:45]

Right? If I find one that's a skill.

**Richard Cheung** [00:21:49]

I'm not sure I have a skill here, but it can also suggest, for example.

**Richard Cheung** [00:21:54]

a new skill for me to, like, for, triaging, like, hardware requests and device issues, right? And so, even if you don't have any skills set up, right?

**Richard Cheung** [00:22:03]

or if you're, you know, your skill set's not complete, as you work through things, right, Catalyst and Serval itself will actually suggest you skills or workflows that you should add.

**Richard Cheung** [00:22:15]

So that's kind of skills. I'm going to pause here for any questions around skills or anything.

**Davison Chung** [00:22:21]

think.

**Richard Cheung** [00:22:21]

I'm gonna add Davison.

**Davison Chung** [00:22:23]

We're skipping ahead a little bit, but, Richard, when would you use a skill versus a knowledge article?

**Richard Cheung** [00:22:31]

Yeah, that's a great question. So, the way I like to think of it is that they're actually pretty similar, and so this is, like, sometimes gets a little, confusing, because your help desk agent can reference both.

**Richard Cheung** [00:22:43]

Right? But the way I like to think of it is that your knowledge base is kind of like your…

**Richard Cheung** [00:22:48]

Then your organization's information bank.

**Richard Cheung** [00:22:52]

Whereas skill is how should your agent actually interact with things, right? So let's take, like, PTO for an example.

**Richard Cheung** [00:23:00]

Maybe you don't want to put your entire PTO policy into a skill, right? Because maybe your PTO policy will change. And as you noticed.

**Richard Cheung** [00:23:09]

Right? Like, changing the skill, you gotta, like, publish it, you know, you gotta, you know, you gotta draft it and then publish it, and we designed it this way because skills should tell your agent how to behave, but maybe in your skill, you tell the agent, hey, reference your knowledge base and your knowledge articles around PTO for the latest PTO policy.

**Richard Cheung** [00:23:29]

And so, really, the skill is kind of teaching our agent, hey, these are the things to look for, right? First of all, look at the knowledge base for PTO policy, then maybe run workflows against Workday or another, like, HR system to look to see, you know, how much PTO the users used.

**Richard Cheung** [00:23:45]

Right? But kind of separating that out into, like, the actual policies live in your knowledge base, but how you want to use that policy and how you want to interact with the user about that policy lives in the skill. It's kind of how I like to separate skills and knowledge.

**Davison Chung** [00:24:03]

Yeah, definitely. I probably, you know, I think this is a good example, I think this PTO one is a good example, because it does use all three, and, you know, I think one thing we'll note is, like, the help desk agent is pretty good about knowing, you know, in some of these basic cases, right, it's pretty good about knowing, okay, if I have three knowledge policies.

**Davison Chung** [00:24:24]

you know, one for the US, one for Canada, one for Mexico. It's pretty good about knowing when to reference those, but it might not know

**Davison Chung** [00:24:33]

you know, intuitively that it needs to ask every single time on a PTO request where someone is from. It'll get there eventually, but if you want to just make sure that the behavior is really good, that's where a skill comes into play and can really guide it through those steps, and can also point it to the source of truth, right? You can tell it, hey, use this very specific workflow that, you know, has a deterministic outcome that will definitely give the right location for the employee every single time.

**Davison Chung** [00:24:58]

to then route you to what is the right knowledge article, and be super specific about it. And so, a good example for how you can combine all three of these. And a little bit of a preview to what you might see in our 104 course, which goes over knowledge bases in more detail. But yeah, with that, why don't we move on to whatever you had next?

**Richard Cheung** [00:25:18]

Awesome, yeah. That's, that's a great call out there. And so, next thing I want to go over are triggers for workflows. So now we've seen workflows and skills, right, but to kind of go back to workflows.

**Richard Cheung** [00:25:29]

You know, how can you actually trigger them? Because in our example of resetting the password, this is just something that, you know, you would run when it's either requested by the user or when the agent wants to run it.

**Richard Cheung** [00:25:41]

But really, there's all different kinds of ways that you can run these workflows. And you can see this within what we call our workflow types, right? And so…

**Richard Cheung** [00:25:50]

You know, these are kind of like the different triggers that you can use.

**Richard Cheung** [00:25:53]

For example, I can have workflows that run on a schedule, right? So, for example, one example is, like, maybe I want to, like, periodically check for.

**Richard Cheung** [00:26:04]

we periodically check for the health of, you know, my employees' laptops, right? Or I want to, like, periodically push updates to somewhere. That can be done with a scheduled workflow.

**Richard Cheung** [00:26:14]

I can also have webhooks, right? And so, if you remember the example in the beginning of, like, hey, if a user is deactivated in some external system, I want to run Serval to then, you know, deactivate from some other systems, or do something in Serval, that's something I can do with webhooks, that external systems can then call into Serval.

**Richard Cheung** [00:26:34]

But, you know, I can also have events that, I can also have workflows triggered from different events within Serval itself, right? And so we kind of have, like, kind of a big laundry list here, but, you know, just highlighting a few, whether it's, like, maybe after I create a ticket, I want to do something, or whenever there has been a reply.

**Richard Cheung** [00:26:52]

Or maybe I want something when the run failed, right? When my workflow run has failed.

**Richard Cheung** [00:26:57]

want to notify, you know, some admin. So these are all the different kind of things that you can do to augment your workflows, to really, you know, define, like, more granular, hey, when should these workflows run? Just be… and beyond just, like.

**Richard Cheung** [00:27:12]

Triggered from a help desk agent, or triggered from a user, for example.

**Richard Cheung** [00:27:17]

Cool. Any questions on workflow types or workflow triggers before we dive into background agents?

**Richard Cheung** [00:27:27]

Cool.

**Davison Chung** [00:27:28]

I think one thing I'll call out is,

**Davison Chung** [00:27:33]

Think, you know, when you're thinking about

**Davison Chung** [00:27:35]

setting up workflows, thinking about what… when do you really want it to be triggered, and when do you want it to run? I think that there's a tendency to just schedule workflows on super, frequent cadences, rather than build them off of a true trigger or an event-based trigger, and I think that that can often be sort of a crutch to achieving what you ultimately want. And so, rather than saying, hey, trigger off of XYZ event.

**Davison Chung** [00:28:00]

A lot of people will set up workflows that are, like.

**Davison Chung** [00:28:03]

hey, just look for this event every minute, right? And I think while that might be easier to set up in the short term, it'll… it'll be detrimental to the performance in the long term. And so, definitely thinking about what is the most streamlined and efficient way of doing this, not just, like, what gets the job done up front in some of these jobs.

**Richard Cheung** [00:28:22]

Yeah, for sure. I think definitely, like, being kind of prescriptive and really thinking through, hey, when exactly you want workflows to run, and what kind of triggers that you need for them, can really kind of add a lot of power to how your Serval instance operates as well.

**Richard Cheung** [00:28:38]

Cool. And let's go into background agents.

**Richard Cheung** [00:28:41]

Right, so…

**Richard Cheung** [00:28:43]

as a kind of refresher, right? Background agents, honestly one of my personal favorite sections to cover, because you really can see… this is when you really get that kind of, like, aha moment in Serval of what you can… kind of the power of things that you can do.

**Richard Cheung** [00:28:56]

And so, as a reminder, background agents are really just agents that you define.

**Richard Cheung** [00:29:01]

That go out on their own, and can do their own investigations, run workflows, provide you reports, suggestions, and kind of really do things on their own and on their own schedule.

**Richard Cheung** [00:29:14]

And so, when I land on background agents, right, what you'll see here is, you know, how I can set up my background agent, right? So I can honestly just describe to Catalyst the kind of agent that I want to set up in natural language.

**Richard Cheung** [00:29:28]

But we also have a few that we've seen.

**Richard Cheung** [00:29:31]

As useful across, you know, many of our customers, so we've provided them pre-installed here.

**Richard Cheung** [00:29:37]

And some really good ones are things like a daily ticket digest, right? So, you know, every 24 hours.

**Richard Cheung** [00:29:43]

Let's, highlight the tickets that need the most attention, let's take a look at how many tickets were closed, let's provide those statistics for us, right? So that's one example of an agent.

**Richard Cheung** [00:29:54]

Another… some other cool ones are the Knowledge Config Scan is really popular, and so what this does is it actually goes ahead and, you know.

**Richard Cheung** [00:30:03]

I know we were covering knowledge in a separate topic, but you can imagine that once you have kind of your different knowledge sources set up.

**Richard Cheung** [00:30:09]

One thing that's really kind of annoying with knowledge sources in general is that things drift, right? Things drift, things contradict, things conflict, and so having this scanner really, kind of scan through your entire knowledge base periodically and help you do that cleanup is super-duper helpful.

**Richard Cheung** [00:30:29]

Another cool one is this license reclamation one, right? So, you can imagine if you have Serval connected to, kind of, your different systems and integrations, we can scan for licenses that you have, and we can scan for, hey, who's actually using those licenses, and what can we reclaim? And so you can set this to kind of, like, work on a schedule as well.

**Richard Cheung** [00:30:49]

So let's say you've had already some background agents set up. What does this actually look like when they go and, you know, do their thing, right?

**Richard Cheung** [00:30:56]

So in this example, what I have here is an example of my software spend reclamation agent, right? And so at a high level.

**Richard Cheung** [00:31:03]

This agent will look at my software asset management things, and it will tell me, hey, these are the different kinds of… these are the licenses that you have, this is what we should reclaim, this is how much you will save.

**Richard Cheung** [00:31:16]

Right, and so you'll notice that your background units will come back with a kind of finding card like this, which is really like a summary of, first of all, like, what it found, right? It'll tell you the highlights. So, for example, you know, it's given me these three highlights here about the, the different, licenses and the different apps that I should reclaim.

**Richard Cheung** [00:31:35]

You can also see, like, kind of a log of the activity on a summary of the activity that this background agent did as it did its investigation. What's really cool here is I can actually view this full report.

**Richard Cheung** [00:31:46]

Right? And so this is really, like.

**Richard Cheung** [00:31:47]

a kind of, like, fully detailed and well-formatted report that I can then go and see, hey, right, complete with, like, charts and everything, right? Exactly kind of the statistics of, you know, of what I found, right? It's telling me, you know, where I'm spending the most amount of money in these subscriptions.

**Richard Cheung** [00:32:04]

Right? And kind of, like, also, like, who are the, what are the largest opportunities here, and who's accountable for them?

**Richard Cheung** [00:32:11]

And so, really, I can provide a lot… I can really, like, periodically generate a lot of these reports, which, you know, before would take a lot of time for an analyst to build, and to build them manually and kind of, you know, build them

**Richard Cheung** [00:32:24]

build them, like, every week or every month or so, I can have Catalyst and the background agent automatically push this information to me. And so I have this information when I need it, not having to kind of, like, reach out to get it built whenever I want it.

**Richard Cheung** [00:32:40]

And so this is something that, like, can really… this kind of, like, reports feature and the fact that background agents can go ahead and do its own investigation really unlocks a lot, in terms of, like, insights and reporting as well.

**Richard Cheung** [00:32:54]

Another thing I want to call out here is, and we kind of went over this too, the suggestions that come with your background agents, right? And so, you know, when you have a suggestion, it kind of looks like this.

**Richard Cheung** [00:33:07]

Right? Where you'll notice that this is kind of like the workflow. For example, in this case, it's suggesting me of a new workflow to build, and so it suggests… you can see here, kind of like in the workflow panel, I can see the details about, about this workflow. I can also see, like, the code that comes with it, and the exact thing that it's gonna build.

**Richard Cheung** [00:33:26]

And so you can really, with this kind of, like, reports and with suggestions, you can really see the.

**Richard Cheung** [00:33:34]

You can start to see how this

**Richard Cheung** [00:33:36]

How, with these two kind of things, you can start to see how it's not, like, information that you have to get, right, and you have to, like, prompt for it, but it's information that you can view, and that's pushed to you.

**Richard Cheung** [00:33:49]

And so I think that's really cool, a really cool thing that background agents unlock for us.

**Richard Cheung** [00:33:55]

And to kind of showcase.

**Richard Cheung** [00:33:57]

what exactly the configuration of background agents looks like. It's really pretty simple. So if you recall, right, this, this software spend reclamation agent that provided us this report.

**Richard Cheung** [00:34:09]

This is actually how it's configured, right? So, after you use Catalyst inside of your background agent, this is the thing that you'll see.

**Richard Cheung** [00:34:15]

Right, you'll see here that really all it is is a set of instructions that you give it, right? And again, these are just instructions in natural language, right? Things to call off for, how it should generate the report, maybe, you know, different workflows that it should run.

**Richard Cheung** [00:34:30]

So you have your instructions, and then you also have your trigger, right? And so…

**Richard Cheung** [00:34:36]

you know, this is the kind of schedule that you set this background agent to run on. Right here, I have it set to daily, every day, but of course, I can set it to either hourly, weekly, or monthly, and so there's degrees of customizations there. And really, with these two, you already have the basics, right, of your background agent.

**Richard Cheung** [00:34:55]

The other things that you see here are around permissions.

**Richard Cheung** [00:34:59]

workflows, approved workflows, and notifications, right? And so what permissions is, is that

**Richard Cheung** [00:35:06]

You can define who this background agent should run as. Because background agents are not allowed to just do everything, right? Background agents can only run with the permissions that you have. Or in this case, in the permissions that

**Richard Cheung** [00:35:20]

is defined from here, right? So if I set this to Spencer, this background agent runs with Spencer's permissions. If I set it to myself, it runs with my permissions.

**Richard Cheung** [00:35:29]

And so really, you… from this, you kind of can control the degree of access that your background agent has. The way I like to think of it is that, you know, when I set up a background agent, it shouldn't do anything that I can't do. But it should be able to do the things that I can do as well. And so this is kind of how I can define these permissions.

**Richard Cheung** [00:35:49]

Now, you also see here a section called approved workflows, right? Because by default, your background agent can only run workflows that read data, or that read things from an external system. Your background agents are not allowed to, like, write things to external systems, or perform

**Richard Cheung** [00:36:07]

actions on external systems, right? This is because we don't want these background agents to just go, you know, run away and just be resetting everyone's Okta passwords, for example.

**Richard Cheung** [00:36:17]

But, you know, if there are workflows that you want your background agents to be allowed to run, you can add them here.

**Richard Cheung** [00:36:23]

And then the last section is around notifications. You know, I can set, who should be notified.

**Richard Cheung** [00:36:29]

you know, and when I should be notified. For example, like, if a report is ready, or when actions are required, or maybe even just I want to be notified of every session that's run, right? And so, I can really kind of control the different behavior of my background agents this way.

**Richard Cheung** [00:36:46]

Cool, that's all I have for background agents in terms of, you know, things that I want to show, but happy to dive into any questions or anything specific that you guys want to…

**Richard Cheung** [00:36:57]

See?

**Davison Chung** [00:36:58]

Yeah, thanks, Richard. I think my two notes on background agents that I would add is, like, one, background agents are the way that you can make Serval self-healing, self-improving over time, and so they're super powerful, and the ones that Richard flagged are really good places to start with the Automation Finder, as well as.

**Davison Chung** [00:37:17]

As well as the knowledge base conflict.

**Davison Chung** [00:37:19]

Resolver, I'm not sure what the exact title is.

**Davison Chung** [00:37:21]

Those are

**Davison Chung** [00:37:22]

Both really, you know, straightforward examples of how you can build self-healing, self-improving system, and I'm sure there's a lot more that you can do. The second thing I'll say about background agents is I think that, and maybe people have experienced this with Claude or with other tools, just like any sort of like scheduled or configured agent there, you do have to think about it a little bit differently than you might normally think about other products, right? You have to build time.

**Davison Chung** [00:37:47]

into your schedule, into your work, to be able to review the work of your agents just like you would of a teammate. And so while they're super powerful, they're more powerful when you start to think about how you can integrate them well into your week. And so for myself, I know that I kind of treat it like having a direct report or a team of direct reports. And so I'll have 30 minutes on my calendar every week to make sure that I'm actually reviewing the work of my agents, reviewing the

**Davison Chung** [00:38:12]

work that is being brought to me, reviewing automation opportunities that it's surfacing.

**Davison Chung** [00:38:17]

And finding ways to make sure that we're taking into account all the work that it's doing on your behalf.

**Davison Chung** [00:38:23]

rather than just leaving you with a bunch of reports that get left unread. And so I think that's an important part of setting up and using background agents that can sometimes go unnoticed.

**Richard Cheung** [00:38:35]

Awesome, yeah.

**Richard Cheung** [00:38:37]

Yeah, I think background agents really are kind of… when you start to see, hey, these… really, there's a whole world of possibilities that this unlocks.

**Davison Chung** [00:38:46]

Yeah, absolutely.

**Davison Chung** [00:38:48]

Cool. Well, I don't see a lot of questions, honestly, in the chat or Q&A. I'm gonna let people, think a little bit about what they might want to see. We'd be happy to show you, what it looks like to build anything that's, you know, specific to your instance, you know, if there's a specific process, or that you'd like to automate, or see how a background agent might build it, or think about how you might approach a scenario, please let us know in the chat, or

**Davison Chung** [00:39:12]

or raise your hand, and we can call on folks and work through it live together. Otherwise, I will give a quick plug for what we have going on the rest of the week, and so Richard went over this a little bit at the beginning, but this is the second course of our 101 series within Serval School. Serval School is our webinar series aimed at getting folks 100% up to speed on all the different

**Davison Chung** [00:39:37]

services or areas of Serval, we've broken it up into a 101 and a 2… or sorry, a 100 series and a 200 series set of courses.

**Davison Chung** [00:39:44]

And this is also a way that you can get Serval certified, and so if you're interested in earning a product certification.

**Davison Chung** [00:39:52]

All you have to do is attend all of our

**Davison Chung** [00:39:55]

100 and 200 series webinars. From there, you'll be eligible to take our certification exam, which is 50 questions, multiple choice, and if and when you pass that, you will be officially Serval Certified and get your certification badge, etc, that you can share with

**Davison Chung** [00:40:13]

all of your friends, colleagues, loved ones, LinkedIn connections, whatever else you would want to do. And so, all the information on

**Davison Chung** [00:40:19]

future sessions on on-demand sessions, as well as the process for getting Serval certified can be found at serval.com slash serval dash school. I put a link in the chat for anyone who is looking for that. As for this week, we have.

**Davison Chung** [00:40:36]

103, 104, and 105 on Wednesday, Thursday, and Friday, as well as a deep dive on Journeys, which is our 202 course on Thursday. And so, a lot of great s


---

# Serval 103 - Access Management

Transcript from the Zoom Events recording, speaker and timestamp per turn.

**Davison Chung** [00:00:00]

Hi everyone, sorry we're a few minutes late. Welcome to Builder 103, focused on access management. I'm joined here by Ben, who's a member of our

**Davison Chung** [00:00:10]

deployment strategy team, and so he's going to walk you through all the content, but before we get started, just want to remind everyone that this is meant to be an interactive session, so please, please, please use the Q&A section, use the chat, if you have a more complex question, and you… we can take you off mute if you raise your hand with a little raise your hand button at the bottom of your screen. And so, really encourage everyone to

**Davison Chung** [00:00:33]

ask their questions. Ben, Ben here is an expert, and so, no question too small, no question too big. But with that, I'm gonna hand it over to Ben to get us started.

**Benjamin Goldfried** [00:00:42]

Thanks, Davison. So, yeah, like he was saying, welcome to Builder 103 Access Management. And so, what we'll cover today are access management versus integrations.

**Benjamin Goldfried** [00:00:53]

The three P's, manual, linked group, and custom workflow provisioning for applications, roles versus resources, catalysts for access management, and then some extra little tidbits of approval delegation overrides, and then user access reviews.

**Benjamin Goldfried** [00:01:08]

So, the full lifecycle of access is we'll get a request in plain English, we can…

**Benjamin Goldfried** [00:01:16]

conditionally have an approver, but we don't have to. Again, this is… this is configurable right here.

**Benjamin Goldfried** [00:01:22]

we will provision, so either through manual, custom, or a SCIM group, and then upon expiration, if

**Benjamin Goldfried** [00:01:32]

access has been granted for a finite period of time, automatically revoking that access as well. So, I want to go ahead and show you just kind of what this looks like within Slack. So I can say, can I get

**Benjamin Goldfried** [00:01:45]

Standard… Access.

**Benjamin Goldfried** [00:01:47]

So, Claude.

**Benjamin Goldfried** [00:01:55]

And what's gonna happen?

**Benjamin Goldfried** [00:01:56]

is… server will get back to me, and essentially it's going to ask me, hey, how long do you need access for, and why do you need access? So again, you can see right here, it says, how long do I need it, and what's the business purpose for it? So I'm gonna say, I need access for 2 weeks.

**Benjamin Goldfried** [00:02:13]

And to work on the code repository.

**Benjamin Goldfried** [00:02:18]

So, right now I'm working out of Slack. This can be done via email, via Microsoft Teams, or also through the Serval UI itself. And so, I can also view this request in Serval.

**Benjamin Goldfried** [00:02:32]

And you'll see that the messages also link.

**Benjamin Goldfried** [00:02:36]

So I can see here, I requested access, and I just got my access provisioned.

**Benjamin Goldfried** [00:02:42]

And I can see that the deprovisioned has also been scheduled in 14 days, which is what I requested access for. So, after the 2-week period that I requested access for.

**Benjamin Goldfried** [00:02:53]

Serval knows to also, excuse me, automatically go and deprovision access. I can also alternatively just end my access early, so I'm going to go ahead and do that.

**Benjamin Goldfried** [00:03:05]

But I just wanted to highlight, essentially, like, this is how easy it is to request access within Serval to an application. All I do is I type in natural language exactly what I need, go back and forth with Serval, giving it reasons for why I need access and how long I need access. Again, both of these are configurable, and we'll talk a little bit more about that later.

**Benjamin Goldfried** [00:03:25]

But I just wanted to highlight

**Benjamin Goldfried** [00:03:28]

the end state that we will be achieving. With Serval.

**Benjamin Goldfried** [00:03:34]

And so…

**Benjamin Goldfried** [00:03:35]

The next thing that I wanted to highlight is a common misconception between applications within integrations and then applications within manage access. So you can see when I toggle between the two, I have a lot more applications within

**Benjamin Goldfried** [00:03:50]

manage access than I do within integrations. And so the reason for that is I only have to integrate an application if I want to run automations on it. So if I run a one… if I want to run workflows on that, essentially.

**Benjamin Goldfried** [00:04:05]

And the reason being for that is when I integrate an application, what I'm essentially doing is I'm allowing Serval to go and call the APIs of this external application.

**Benjamin Goldfried** [00:04:17]

When I think about an app within access management, however, I think about a user saying, I need access to this application. So it's fundamentally a different use case. So again, to highlight integration, I would integrate an application that I want to run automations on, I would add an application to access management when I want to allow users to request access

**Benjamin Goldfried** [00:04:39]

to this application.

**Benjamin Goldfried** [00:04:43]

So, let's jump into… well, what is it? What does provisioning access and setting up access management within Servo actually look like? So, if I click on Figma here, you'll see that we have 3 different roles.

**Benjamin Goldfried** [00:04:55]

So I have the standard role, this editor role, and this admin role. Again, you can configure all of your different roles within your applications. And so, I'm going to click on Standard.

**Benjamin Goldfried** [00:05:06]

And you can see here, we have the three P's. So we have access profile, Access Policy, and then the provisioning method.

**Benjamin Goldfried** [00:05:17]

And so access profile is really dictating who can request access to this application. So, right now, it's anyone in the organization. I can limit it to team members of our specific team within Serval. I can limit it to also specific groups.

**Benjamin Goldfried** [00:05:36]

I can block specific groups,

**Benjamin Goldfried** [00:05:42]

I can have specific custom fields, specific team members, etc, etc.

**Benjamin Goldfried** [00:05:48]

I can also select multiple access profiles, so if engineers and security should have access, I can select both of those, or I can select only one, or I can leave it as anyone in the organization. But again, to reiterate, access profile is dictating who can even request access to this application.

**Benjamin Goldfried** [00:06:07]

The next part of configuring access within Serval is access policy.

**Benjamin Goldfried** [00:06:15]

And so I can see here, if I edit this policy, these are all of the fields that I can configure within an access policy. So the first is max access length. So right now it's indefinite, but if I want to limit the amount of time that people can have access to a specific application, this is where I would do it. And so, like you saw with Claude, I…

**Benjamin Goldfried** [00:06:37]

limited it to 2 weeks, and so I requested 2 weeks, and then also Serval handles the deprovisioning as well, automatically. So we saw that with Claude, that the deprovisioning was scheduled for 14 days, but again, want to highlight that not only does Serval take care of the provisioning, but it also takes care of the deprovisioning. So really the entire life cycle of

**Benjamin Goldfried** [00:07:00]

Access.

**Benjamin Goldfried** [00:07:01]

Servo can automate for you.

**Benjamin Goldfried** [00:07:03]

And so we can require business justification. So, in the example I showed you with Claude, this was toggled on yes, which is why Serval was prompting me to require, or to give a business justification, but alternatively, I could put that as no. We see a lot of our customers

**Benjamin Goldfried** [00:07:19]

Toggling this onto yes for, like, audit and compliance purposes, but again, totally customizable for your specific

**Benjamin Goldfried** [00:07:27]

Organization and specific roles and applications within those… or sorry, applications and roles within those applications.

**Benjamin Goldfried** [00:07:36]

And then I think the real foundational piece of approvals, or sorry, of access management within Serval is disapproval.

**Benjamin Goldfried** [00:07:45]

So, I can add an approval step, and I can have it be the user's manager, so this is pulled in from whatever IDP you have. I can also have the app owner, the resource owner, or the role owner.

**Benjamin Goldfried** [00:07:58]

So, what all of these are is, if I click out of here.

**Benjamin Goldfried** [00:08:04]

What you can see is I can designate an owner for this specific role.

**Benjamin Goldfried** [00:08:08]

I can designate a role… sorry, an owner for…

**Benjamin Goldfried** [00:08:12]

this specific application. So for Figma, Ashna is the owner, and then I can also schedule or create a…

**Benjamin Goldfried** [00:08:20]

owner for the resource itself. And so, what these owners are…

**Benjamin Goldfried** [00:08:26]

It sounds like they'll get, like, special permissions.

**Benjamin Goldfried** [00:08:29]

But they don't have any actual special permissions. Essentially, what these owners are, it's just a relationship within Serval.

**Benjamin Goldfried** [00:08:37]

that you can use for approvals. So, if you have somebody that typically deals with owning an application, and setting up provisioning, and knows the ins and outs of that application, you can set that person as an app owner, essentially, and then use that reference or that relationship within Serval to have them be

**Benjamin Goldfried** [00:08:55]

the approver.

**Benjamin Goldfried** [00:08:56]

I could also select individuals, I can select multiple individuals if I want.

**Benjamin Goldfried** [00:09:03]

Etcetera.

**Benjamin Goldfried** [00:09:04]

I can have specific groups, so if I pick… this Create Okta group.

**Benjamin Goldfried** [00:09:10]

I can require one of the two members, I can require both of the members. Again, any combination I want. And then, alternatively.

**Benjamin Goldfried** [00:09:19]

we can use a workflow as the approver. And so, a workflow essentially allows for all of the customization and flexibility that your approval process may have. And so, an example that we'll talk about a little bit later…

**Benjamin Goldfried** [00:09:35]

is, for AWS, a lot of companies have an elevated engineering access role, and within this access role, you can imagine you have engineers that are on call.

**Benjamin Goldfried** [00:09:47]

And they should be approved for this elevated engineering role automatically, but if an engineer is not on a call, then maybe we route to the head of security.

**Benjamin Goldfried** [00:09:58]

So that's a great example of a custom workflow, because we have, like, a custom approval procedure. So workflows really allow for all of the flexibility and customization that your business might have when it comes to approvals within Access.

**Benjamin Goldfried** [00:10:19]

So that's access profile and access policy. So, essentially what we've covered, and I kind of think of it almost as a hierarchy.

**Benjamin Goldfried** [00:10:26]

The access profile is, like, the first line of defense. It's dictating, again, who can request access. The access policy is what are the rules with getting access, and once we've gone through those two steps, then it's time to actually provision access, and that's where this mana… sorry.

**Benjamin Goldfried** [00:10:41]

this provisioning method comes into place. And so you can see here we have 3 different ways of provisioning. We have manual, and so right now, I am assigned as one of the provisioners, and so is Sri. I'm going to…

**Benjamin Goldfried** [00:10:55]

get Shree… Sri no longer is responsible for provisioning access.

**Benjamin Goldfried** [00:11:00]

But you can see, I can assign individuals, and I can assign specific groups to be the manual provisioner.

**Benjamin Goldfried** [00:11:08]

We can also have, if I go over here to GitHub.

**Benjamin Goldfried** [00:11:13]

I have a linked group as the provisioning method here. And so, a linked group is really…

**Benjamin Goldfried** [00:11:20]

kind of like the highest level of automation, essentially. So this is where you have a SCIM group configured for the specific role and application, and so…

**Benjamin Goldfried** [00:11:31]

once I add a user to this app GitHub Okta group, then they are automatically pushed into the standard GitHub role, and again, this is because I have skimp configured, and so a custom workflow

**Benjamin Goldfried** [00:11:45]

is useful. If… We don't have SCIM,

**Benjamin Goldfried** [00:11:51]

But the application has APIs that allow us to automatically… that allow us, essentially, to create workflows to call APIs to provision users access to this application. So in the case of Calendly right here.

**Benjamin Goldfried** [00:12:05]

Calendly, I happen to know, gates their enterprise license, or sorry, gates SCIM behind their enterprise license, which you have to pay for, but they do have an API to invite users to an organization. So, what I did was I created a custom workflow to provision Calendly access.

**Benjamin Goldfried** [00:12:21]

I will caveat this with, if you are using a custom workflow to provision access.

**Benjamin Goldfried** [00:12:27]

Since, inherently, what you're doing is creating a workflow for that application, you also have to have it… have that application integrated, because you're calling APIs on behalf of it. So you can see here, I do have Calendly integrated.

**Benjamin Goldfried** [00:12:42]

The other use case that I see a lot of people use custom workflows for is…

**Benjamin Goldfried** [00:12:50]

Let me just pull up a… another role.

**Benjamin Goldfried** [00:13:02]

Is, if you have…

**Benjamin Goldfried** [00:13:05]

a IDP group that's, like, your source of truth for which users have access to this application and role, but you don't have SCIM configured, and you're manually configuring access. So what you can do here is you can combine these manual steps of… or combine these steps of manually provisioning access.

**Benjamin Goldfried** [00:13:24]

as well as adding them to the linked group. So this way.

**Benjamin Goldfried** [00:13:28]

Again, you're still following, like, your correct provisioning procedure of

**Benjamin Goldfried** [00:13:32]

manual provisioning, as well as adding them to the linked group, but now we're not relying on, like, SCIM, essentially, to provision our access. It's more of, like, an extra bookkeeping task.

**Benjamin Goldfried** [00:13:48]

So those are the three P's. Again, just to highlight.

**Benjamin Goldfried** [00:13:52]

Access profile, who can request access, access policy, what are the rules with getting access, provisioning method, how are we actually giving somebody access once they've been approved for this application?

**Benjamin Goldfried** [00:14:05]

So the next thing that I want to talk about is this concept of a role versus a resource. So we can see here within GitHub, I have all these different… I have a standard role, and then I have these two different resources. I have an engineering resource and a repository resource.

**Benjamin Goldfried** [00:14:21]

And within these resources, I have my own roles as well. And so, the way I think about roles and resources is a resource is the thing that I'm getting access to.

**Benjamin Goldfried** [00:14:32]

And then a role is the permission within the that resource. So…

**Benjamin Goldfried** [00:14:39]

I think GitHub is a pretty good example. So we can see here… see here, we have this repository resource. So…

**Benjamin Goldfried** [00:14:47]

The reason that this repository is a resource is because it's this thing that I'm getting access to. I'm getting access to this repository.

**Benjamin Goldfried** [00:14:54]

And then within this repository, I have different roles. So I have different permissions within the repository. I have a read-only permission, so if I'm allowed to just look at the code, and then I have a write access permission as well. So if I'm allowed to actually make edits to the code, too.

**Benjamin Goldfried** [00:15:10]

So…

**Benjamin Goldfried** [00:15:12]

That's a really powerful, like, configuration within Servo as well for kind of abstracting all of these different concepts.

**Benjamin Goldfried** [00:15:20]

And so, what we just did was, we walked through, essentially, like.

**Benjamin Goldfried** [00:15:25]

if I was to add an application and create app, and go and, like, create all these resources by hand.

**Benjamin Goldfried** [00:15:32]

That's essentially how we would do it. We would create all those access profiles, all those access policies, and then provisioning method.

**Benjamin Goldfried** [00:15:40]

And so, the reason that I like to highlight that.

**Benjamin Goldfried** [00:15:44]

even though that part is kind of a manual process, like, for the IT agent, is because it really gives us a foundational understanding of, like, what are we looking for.

**Benjamin Goldfried** [00:15:54]

when we're provisioning, or when we're setting up access management, rather. We're looking for who can request access.

**Benjamin Goldfried** [00:16:00]

How long is their business justification required?

**Benjamin Goldfried** [00:16:04]

Are there any approvers?

**Benjamin Goldfried** [00:16:06]

And then how are we actually provisioning?

**Benjamin Goldfried** [00:16:09]

access. And so, what we can do is we can actually use Catalyst in the future To go and…

**Benjamin Goldfried** [00:16:17]

create these applications and these roles and these resources within applications for access management. So if you're a first-time user of Servil, I would recommend going through the process manually once, like we just did, and then once you have that foundational understanding and you've kind of walked through the motions, I kind of think of that as, like, graduating from that step and then moving on to Catalyst.

**Benjamin Goldfried** [00:16:39]

And so you can see here with Catalyst.

**Benjamin Goldfried** [00:16:43]

I just gave it a prompt, and I said, I want to create an AWS instance that users can request access to. There should be a role called Elevated Engineering Access, and anyone can request access. Users should be able to log on and get access for 1 hour maximum.

**Benjamin Goldfried** [00:17:00]

If a user is part of this on-call group, then they're auto-approved, but if not, then they're routed to our head of security for approval.

**Benjamin Goldfried** [00:17:09]

And then access is provision.

**Benjamin Goldfried** [00:17:11]

Via this linked group.

**Benjamin Goldfried** [00:17:13]

So you can see here.

**Benjamin Goldfried** [00:17:15]

how I'm essentially leveraging my knowledge of access profiles, access policies, and provisioning method while I'm talking to Catalyst. I'm specifying what the role is.

**Benjamin Goldfried** [00:17:27]

I'm specifying who can request access, so the access policy.

**Benjamin Goldfried** [00:17:31]

I'm specifying how long they should be able to get access for, and then I'm also specifying the rule associated with the approval.

**Benjamin Goldfried** [00:17:39]

And then the last thing I'm doing is specifying how it's provisioned. So you can see that I… I basically, like, prompt formula this to be…

**Benjamin Goldfried** [00:17:48]

access his profile, Access Policy And then provisioning method.

**Benjamin Goldfried** [00:17:55]

So we can see here, Catalyst asked me one follow-up, I specified that I want this to just be in access management only, and then it created all these resources right here. So if I click through all these, I can see that it's created this new, like, AWS, instance, it's created this app access resource.

**Benjamin Goldfried** [00:18:14]

it's created the custom approval workflow. So this is looking up, essentially, like, if I'm on call, if I am, auto-approve me. If I'm not, route to the head of security. So this would be our custom,

**Benjamin Goldfried** [00:18:28]

Custom approval workflow.

**Benjamin Goldfried** [00:18:31]

It built out this access policy for me.

**Benjamin Goldfried** [00:18:35]

And you can see here, it specified that the max access length should be 1 hour, so consistent with what I specified here.

**Benjamin Goldfried** [00:18:43]

Business justification is toggled on to no, because nothing in my prompt indicated that we should require business justification.

**Benjamin Goldfried** [00:18:52]

And then we can see that the approval step is this workflow.

**Benjamin Goldfried** [00:18:57]

that we've just created within Catalyst as well.

**Benjamin Goldfried** [00:19:00]

So this is our custom approval workflow, and we can see the last thing is… this role itself.

**Benjamin Goldfried** [00:19:08]

So the role is using anyone in the organization as the access profile, because again, that's what I specified here.

**Benjamin Goldfried** [00:19:15]

It's using this access policy.

**Benjamin Goldfried** [00:19:18]

That we went ahead and just looked at over here that it created.

**Benjamin Goldfried** [00:19:22]

And then the provisioning method is this linked group, which, again, we specified right here. So Catalyst is really, like.

**Benjamin Goldfried** [00:19:30]

your highest lever of automation for configuring access within Serval, and it is primarily what you will be using to configure access. But again, like, having this foundational understanding will allow you to more easily and more, like, seamlessly interact with Catalyst to build out

**Benjamin Goldfried** [00:19:47]

all of these for you, all of these access management configurations for you. So I can publish these one at a time.

**Benjamin Goldfried** [00:19:54]

Or I can publish all of them. I'm going to go ahead and publish all of them.

**Benjamin Goldfried** [00:20:11]

And if I go back to access, what we'll see is we now have this AWS role, or application rather, and we have this elevated engineering access role. And again, it has all of the policies and configurations that we specified in Catalyst.

**Benjamin Goldfried** [00:20:27]

Cool.

**Benjamin Goldfried** [00:20:28]

So, the next thing that I wanted to show is this idea of, like, approval delegations.

**Benjamin Goldfried** [00:20:34]

So you can imagine, if a user goes out of office.

**Benjamin Goldfried** [00:20:40]

You will want to configure some sort of, like, delegator for…

**Benjamin Goldfried** [00:20:45]

acting on behalf of this user. So, tickets assigned to this user and approval requests assigned to this user should route to somebody else, essentially, while I'm out of office. So what I can do is, again, within my profile, I clicked on my profile, and I went to settings, and I can add a delegation rule, so I'm gonna have…

**Benjamin Goldfried** [00:21:03]

George?

**Benjamin Goldfried** [00:21:04]

be my delegator.

**Benjamin Goldfried** [00:21:06]

And I can set an active period. So, if I know I'm going on vacation next week, from Monday to Friday.

**Benjamin Goldfried** [00:21:13]

I can go Monday to Friday, I can specify the time to start and the time to stop as well, and then I can add him as my delegator for this time period.

**Benjamin Goldfried** [00:21:22]

And what we'll see happen is… so I'm going to have it start right now, actually.

**Benjamin Goldfried** [00:21:31]

And… if I show you… Then Manage Access.

**Benjamin Goldfried** [00:21:38]

I am…

**Benjamin Goldfried** [00:21:42]

I am the approver, or sorry, I am assigned to be the manual provisioner for this standard application.

**Benjamin Goldfried** [00:21:48]

So, if I create a new request.

**Benjamin Goldfried** [00:21:53]

And also, I wanted to call out, too, this is something I… I forgot to mention, because I was working out of Slack. If I'm working out of the Serval UI, I can describe in natural language here, like, I need access to Figma standard.

**Benjamin Goldfried** [00:22:08]

And I can submit this. Or alternatively, what I can do is I can go through this request access catalog, and I can see all the different applications I can request access to, and I can see all of the different roles I can request access to. So I'm going to request access to this standard role, business justification, I'm working on design.

**Benjamin Goldfried** [00:22:29]

And I could go ahead and request access.

**Benjamin Goldfried** [00:22:32]

And so, what we're going to see… is…

**Benjamin Goldfried** [00:22:38]

that this, even though I showed you in the configuration, is assigned to me for the manual provisioning.

**Benjamin Goldfried** [00:22:45]

It will be assigned.

**Benjamin Goldfried** [00:22:47]

actually to George, because he is my delegator. So you can see here, there's a task that's been created to provision access.

**Benjamin Goldfried** [00:22:55]

And that is actually assigned to George instead of myself, because I've set him as my delegator.

**Benjamin Goldfried** [00:23:01]

So I can go ahead and I can remove that.

**Benjamin Goldfried** [00:23:03]

Whoopsies.

**Benjamin Goldfried** [00:23:09]

I'm gonna remove George as my delegator. I'm gonna go back to this ticket and cancel it out.

**Benjamin Goldfried** [00:23:17]

Whoopsies

**Benjamin Goldfried** [00:23:20]

So I canceled this task because I'm not actually going to provision access, so that's why you see provisioning failed.

**Benjamin Goldfried** [00:23:27]

But what we can also do, so let's say I forget to set my delegator, within Servo. What I can do is, within Slack.

**Benjamin Goldfried** [00:23:39]

I can go… And… Update my status.

**Benjamin Goldfried** [00:23:44]

And I'll do my status as vacationing, and I'm starting today, and end tomorrow.

**Benjamin Goldfried** [00:23:50]

I can create a workflow within Serval, That will look at…

**Benjamin Goldfried** [00:23:56]

everybody's out of office, or sorry, everybody's status within Slack

**Benjamin Goldfried** [00:24:01]

and then determine if they're out of office, and set a delegator on their behalf. So you can see here, I've just set this vacationing status.

**Benjamin Goldfried** [00:24:10]

What I'm gonna do is I'm gonna manually run this workflow, but again, you can have this workflow run on a schedule.

**Benjamin Goldfried** [00:24:15]

So you don't even have to worry about this, but for demo purposes, I'll run this right now.

**Benjamin Goldfried** [00:24:35]

So it's asking for confirmation, I say yes, run it.

**Benjamin Goldfried** [00:24:54]

And so you can see Serval found that there are 4 users within my Slack workspace.

**Benjamin Goldfried** [00:25:00]

But I'm the only one with a status that indicates I'm out of office. So, my status was vacationing, and Servo was able to use AI inferencing, essentially, to determine that, like, vacationing is fundamentally the same as being out of office. And so, it set my approval delegator to be Varun.

**Benjamin Goldfried** [00:25:18]

So now if I go and I do the same task as before.

**Benjamin Goldfried** [00:25:22]

of requesting access to Figma?

**Benjamin Goldfried** [00:25:30]

But we'll see.

**Benjamin Goldfried** [00:25:32]

is Varun is actually assigned now to be the approver.

**Benjamin Goldfried** [00:25:37]

And you can see here, again, the exact same request, since I am assigned as the provisioner, but I have a delegator,

**Benjamin Goldfried** [00:25:44]

My delegator is Arun. He was now assigned to this ticket.

**Benjamin Goldfried** [00:25:48]

And so I can go ahead, go back to Slack here, and get rid of this status.

**Benjamin Goldfried** [00:25:55]

And I can rerun this workflow.

**Benjamin Goldfried** [00:26:01]

Whoops, that's the wrong one.

**Benjamin Goldfried** [00:26:07]

So I'm gonna run it again.

**Benjamin Goldfried** [00:26:14]

And what we'll see is now that I no longer have an out-of-office status,

**Benjamin Goldfried** [00:26:24]

Serval's going to remove Varun as my delegator, and it'll now act as myself.

**Benjamin Goldfried** [00:26:45]

So you can see here, it says no out-of-office status, but I previously had one, so that delegation was removed.

**Benjamin Goldfried** [00:26:51]

And so now I can show you, and I'll work out a Slack on this request as well to show you.

**Benjamin Goldfried** [00:26:56]

And I'll say, I need access… actually, let me cancel.

**Benjamin Goldfried** [00:27:02]

this request.

**Benjamin Goldfried** [00:27:03]

In case I didn't already do that.

**Benjamin Goldfried** [00:27:09]

And the reason I'm canceling this request is because Serval's smart enough to know, essentially, like, if I have provisioning that's outstanding, and I request access again, it's gonna deny my request and say, essentially, like, you already have your out… you already have a…

**Benjamin Goldfried** [00:27:25]

outstanding access request. So I'm gonna say, again, like, I need access to Figma standard.

**Benjamin Goldfried** [00:27:48]

So it's requesting standard Figma access for me. I can, like, follow along, essentially. And you can see here that it's pending provisioning from myself here. And so, if you notice over here.

**Benjamin Goldfried** [00:27:59]

I just got… N…

**Benjamin Goldfried** [00:28:02]

a ping from Serval, telling me that I've been assigned to this task of provisioning access for Figma. So…

**Benjamin Goldfried** [00:28:12]

If you are assigned as the manual provisioner, if you are assigned as an approval, etc, etc, Servo will send you a DM, essentially alerting you to this information.

**Benjamin Goldfried** [00:28:23]

Which is pretty neat. So I can mark it as done, or I can cancel it. Again, I'm going to cancel it.

**Benjamin Goldfried** [00:28:29]

But just wanted to call out that that is possible within Serval. And again, I can see this ticket, and I can see all the progress.

**Benjamin Goldfried** [00:28:39]

But just highlighting that those delegation rules were… In fact, being used.

**Benjamin Goldfried** [00:28:49]

And again, you can see it was assigned to myself, which is, like, how we configured. In those two other examples, it was assigned to George and assigned to Varun, because they were set as my delegators.

**Benjamin Goldfried** [00:28:59]

So the next thing that I want to show within Access is…

**Benjamin Goldfried** [00:29:04]

If I go, and I say, I need access, to Figma Admin.

**Benjamin Goldfried** [00:29:15]

And we can follow this along within Serval.

**Benjamin Goldfried** [00:29:23]

Figma admin access on my,

**Benjamin Goldfried** [00:29:27]

on my team is configured… oh, okay. So you can see I already have…

**Benjamin Goldfried** [00:29:32]

a request in progress here. So it's gonna deny it. So I can view my existing access request.

**Benjamin Goldfried** [00:29:37]

Now I'm going to…

**Benjamin Goldfried** [00:29:42]

Cancel.

**Benjamin Goldfried** [00:29:44]

this request. So that's what I was talking about before.

**Benjamin Goldfried** [00:29:49]

I'm gonna go ahead and rerun this, essentially.

**Benjamin Goldfried** [00:30:03]

Gonna view this in serval, and so within my team, I've configured… Figma Admin Access.

**Benjamin Goldfried** [00:30:14]

to have SWETHA as an approver.

**Benjamin Goldfried** [00:30:18]

So if I go to this ticket.

**Benjamin Goldfried** [00:30:23]

What we're going to see is my access is going to be pending approval from SWETHA.

**Benjamin Goldfried** [00:30:49]

So you can see here that I'm waiting for approval. Within this access request, you can see I'm awaiting approval from SWETHA as well.

**Benjamin Goldfried** [00:30:59]

I think I have slow internet, so let me try and refresh my page here.

**Benjamin Goldfried** [00:31:05]

Yeah. So what you can see here is it's requesting me admin access.

**Benjamin Goldfried** [00:31:10]

But this request requires approval.

**Benjamin Goldfried** [00:31:12]

So we can see here I'm waiting on Swetha to be the approver. But you can imagine a scenario, again, of, like, maybe Swetha's out of office for the day, and she forgot to set her delegator. But for some reason, I, like.

**Benjamin Goldfried** [00:31:24]

urgently need access to Figma Admin.

**Benjamin Goldfried** [00:31:28]

The state of things right now is that I'd just be blocked indefinitely until Swetha comes back. But that's not really realistic for the scenario I was describing, like, maybe Swetha is just away from her computer for whatever reason.

**Benjamin Goldfried** [00:31:41]

So, within Serval, as a team manager, what you can do for, like, an emergency escape pass, essentially, to unblock somebody, is click this little pencil icon, and click override and approve. Again, this action is only available to team managers.

**Benjamin Goldfried** [00:31:58]

So, I am a team manager within this team workspace, so I'm going to override and approve.

**Benjamin Goldfried** [00:32:05]

And what you'll see is that it's going to say it was approved by myself.

**Benjamin Goldfried** [00:32:09]

And so, within your audit logs, so your audit logs can be found within organization.

**Benjamin Goldfried** [00:32:15]

Organization can only be… is only accessible to organization admins, as well, so I just want to call that out, but within settings.

**Benjamin Goldfried** [00:32:24]

I will go to audit logs, and you can see here that I had a team override approver decision with a level of warning, which audited essentially exactly this action that I took.

**Benjamin Goldfried** [00:32:34]

So, that action should only be used as an emergency escape hatch, essentially, and I wanted to call out that it is audited, for compliance purposes as well, so you don't have to worry about a team manager that's going, running wild, and, like, approving everything without any, like.

**Benjamin Goldfried** [00:32:50]

tail of the fact that they were doing that. This is, in fact, audited.

**Benjamin Goldfried** [00:32:56]

And you can see it in those audit logs.

**Benjamin Goldfried** [00:33:00]

And then the last thing that I wanted to highlight… is…

**Benjamin Goldfried** [00:33:04]

user access reviews. So I've talked about setting up access management for users to request access. The next kind of, like, logical path is that, okay, once a user has access, like.

**Benjamin Goldfried** [00:33:16]

how do I… how do I audit this, essentially? Like, how do I see who has access to what and verify if they still should have access, revoke it if they shouldn't, etc, etc. And so that's where user access reviews come into play.

**Benjamin Goldfried** [00:33:29]

This is currently gated behind a feature flag, so if you don't see this within your organization, reach out to whoever your deployment point of contact is to enable it for you, and then you should see it show up within

**Benjamin Goldfried** [00:33:45]

Capabilities as well, and you would just toggle it onto… Yes.

**Benjamin Goldfried** [00:33:53]

So within user access reviews, I can create a new review, so I'll just call it… Test, review…

**Benjamin Goldfried** [00:34:00]

9 slash 16.

**Benjamin Goldfried** [00:34:03]

And I can describe a purpose. I can also set a target completion date, so I can set it for September 25th.

**Benjamin Goldfried** [00:34:08]

And this target completion date is useful, like you can see here, for sending out reminders.

**Benjamin Goldfried** [00:34:14]

So I can send out due date reminders, and that will be based off of what this target completion date is. And then I can also set a review policy. So this is kind of synonymous, essentially, with the access policy, but this is more for user access reviews specifically. So if I go and create this policy.

**Benjamin Goldfried** [00:34:32]

There's a couple of different fields that I can configure. The first is, do I want to require a comment on every decision I make? So, whether I certify access for somebody or deny access for somebody, do I need to specify

**Benjamin Goldfried** [00:34:45]

why I'm making that decision, essentially. If the answer is yes, I would toggle this on as yes. If the answer is no, I'd toggle it on as no. You still can specify a decision. If this would toggle on no, it's just not a requirement.

**Benjamin Goldfried** [00:34:58]

Do I want to allow reviewers to review their own access? So if I'm reviewing access for, like, an admin-level role that I have access to, can I review my own access, or do I need somebody else to review it for me?

**Benjamin Goldfried** [00:35:10]

And then the last is, who is actually reviewing each item? So, right now, it's the review owner, so I am the review owner. Essentially, whoever is creating this is their review owner, but I can add extra reviewers as well. So again, this concept of, like, user manager, app owner, resource owner, role owner, specific individuals, or a specific group, I can also set.

**Benjamin Goldfried** [00:35:31]

So I'm gonna go ahead and continue to scoping.

**Benjamin Goldfried** [00:35:35]

And so there are two different ways that I can scope an application, or scope, like, which roles and resources within applications I want to certify or deny users access to. The first is manual scope.

**Benjamin Goldfried** [00:35:47]

So this is all of the applications I have configured within Manage Access. This is going to show up here. I can go in, see all of the different, like, roles and resources. I can select, like, specific roles, I can select a resource as a whole, or I can select the entire application.

**Benjamin Goldfried** [00:36:05]

And so you'll see all of these. The other option is a tagged-based scope. So, within an application.

**Benjamin Goldfried** [00:36:13]

something like AWS.

**Benjamin Goldfried** [00:36:15]

I can tag specific applications, or I can tag specific roles. So what I can do here is I can add this admin tag that I've created, because this role corresponds to, like, an admin.

**Benjamin Goldfried** [00:36:29]

you'll see I also have, like, Figma Admin tagged as admins, and…

**Benjamin Goldfried** [00:36:36]

That might have been… that might be all of my admin groups. But essentially, it just allows you another way of configuring,

**Benjamin Goldfried** [00:36:45]

What specifically, like, the scope is?

**Benjamin Goldfried** [00:36:56]

So that's what tag-based scope would be. So I'm gonna go ahead, and we're gonna go through a manual scope, and so I'm gonna do just all of GitHub, and I'm gonna save that scope, and I can see that there's 5 roles, 3 resources, again, essentially like what we were showing before. And now I'm gonna prepare the review, and what Serval's going to do, it's going to pull in all of the users

**Benjamin Goldfried** [00:37:15]

With this, that fall under this category. So all of these people have…

**Benjamin Goldfried** [00:37:23]

Sorry, not all these people. Shreya has engineering admin access.

**Benjamin Goldfried** [00:37:28]

Varun has GitHub repository right access, and so you can see here, like, the specification of, really, what users have access to what.

**Benjamin Goldfried** [00:37:36]

So I'm gonna launch this test, and you'll see here I have this all review tasks. So this is, like, the admin view of all outstanding tasks. It just so happens that I am also the reviewer of all of these, but if I'm not the reviewer for one of these, so let's say I change the reviewer

**Benjamin Goldfried** [00:37:53]

to be… Alan.

**Benjamin Goldfried** [00:37:57]

In this scenario, and I get rid of myself.

**Benjamin Goldfried** [00:38:04]

you'll see that I still see it within my tasks here. So I have 12… there are 12 tasks, because again, this is, like, the admin view, but within my pending tasks, I only have 11, because I just got rid of one for myself.

**Benjamin Goldfried** [00:38:19]

So, within my pending tasks, what I can do is I can certify or deny, somebody access. So, Shreya, I see she has engineering admin access. I'm going to go ahead and deny her access. I see that Jordan has engineering admin access. I'm also going to deny, but I'm going to specify that she changed roles.

**Benjamin Goldfried** [00:38:38]

Which is why she no longer needs access.

**Benjamin Goldfried** [00:38:40]

But Varun has GitHub repository right access. He actually does need that access, and I see that

**Benjamin Goldfried** [00:38:47]

Derek also has GitHub repository Right Access. I'm going to certify that and say, provide a comment that it's needed for his current role.

**Benjamin Goldfried** [00:38:57]

So I'm gonna go ahead and skip the rest, and I can see what's in Submitted over here, all of the different reviews that I've submitted. And so, I want to call out that my decision is not binding up until this point.

**Benjamin Goldfried** [00:39:10]

So, even though I've denied access, I haven't actually gone and revoked their access to this application. I can go ahead and say, oh, whoopsies, I accidentally misclicked, and she's on deny, but I want to certify.

**Benjamin Goldfried** [00:39:23]

I'm gonna go ahead and actually certify. So you can see you can change your decision still up until this point.

**Benjamin Goldfried** [00:39:30]

I also want to call out that we have this configuration so you can see, essentially, like, what roles, what resources we are reviewing right now. You can see what the review policy is, and then you can also configure, even still, what your notification policy is.

**Benjamin Goldfried** [00:39:45]

And then the last thing is we have this concept of reports. So I can generate a CSV or an Excel document.

**Benjamin Goldfried** [00:39:52]

of a report of, like, all of the different decisions, essentially, that have been made. And then, finally, I can end this review.

**Benjamin Goldfried** [00:40:01]

So I'm gonna skip the rest and end, and once I've ended this review, you see that we have this remediation tab pop up here.

**Benjamin Goldfried** [00:40:08]

And so, this remediation tab is how we would actually go about revoking access. So I'm going to hit Trigger Remediation, and you can see here we have these two separate users, that I separately revoked their access for. And so, only once I hit Trigger Remediation

**Benjamin Goldfried** [00:40:25]

Is their access actually revoked? So again, I want to be, like, very explicit that this is by design.

**Benjamin Goldfried** [00:40:33]

If you've made a mistake, you don't have to trigger the remediation. It's only once you explicitly go ahead and give Servo the go-ahead to revoke their access will it go ahead and actually do that.

**Benjamin Goldfried** [00:40:47]

So, that was all I had on my agenda for covering access management. If there's any questions, Davison, I would love to answer those now.

**Davison Chung** [00:40:58]

Amazing. Thank you, Ben. I think that was a really great run-through, and I just want to emphasize as well that setting up access management correctly in Serval is one of the most impactful levers on your automation rate and on, time savings for your teams.

**Davison Chung** [00:41:15]

And it can be super, super powerful for a lot of use cases that are, outside of the bands of typical access management, things like just-in-time access, or very conditional access for, you know, I think that the GitHub example of having access to different repos with different permissions, in different scenarios is also super powerful. So, highly recommend everyone, think through what is top of mind for them, and ask about any

**Davison Chung** [00:41:40]

And all questions that you have while we're on the call here.

**Davison Chung** [00:41:43]

While you're thinking of those questions or jotting them down, I do want to just give a plug for future sessions we'll have for the rest of this week.

**Davison Chung** [00:41:51]

I'll put in the chat where you can, register for future sessions, but we have tomorrow, our session on knowledge, analytics, and campaigns, as well as a special session in the afternoon focused specifically on Journeys, which is our,

**Davison Chung** [00:42:10]

which is our product for cross-functional team processes, things like, onboarding, offboarding, joiner, mover, lever type workflows. And then on Friday, we have a session

**Davison Chung** [00:42:22]

On governance, teams, and permissions that will go more into the admin side of how to set up your server instance, and govern it well.

**Davison Chung** [00:42:31]

And so, we'll just give those quick plugs, and I'm gonna throw the registration link in

**Davison Chung** [00:42:38]

The chat right now.

**Davison Chung** [00:42:42]

But yeah, I don't see any questions right now from the group. I think Ben just did an excellent job of covering everything.

**Davison Chung** [00:42:49]

I'll give everyone 30 more seconds, but otherwise, happy to give people 15 minutes back on their Wednesday here.

**Benjamin Goldfried** [00:42:59]

And I also wanted to call out,

**Benjamin Goldfried** [00:43:02]

When we're talking about access within Servo, a lot of times I see customers trying to come up with workflows, like, outside of access, or come up with skills for how access should be configured.

**Benjamin Goldfried** [00:43:13]

I always try and caution against that, and really, like, any… anytime someone's requesting access, that should really be a configuration within Manage Access itself, and Servo does a really good job of handling

**Benjamin Goldfried** [00:43:27]

those scenarios. And the reason that I caution against, like, coming up with

**Benjamin Goldfried** [00:43:31]

one-off skills or one-off workflows to try and accomplish the same task that Manage Access accomplishes is, one, access management is first class within Serval, so you're kind of having, like, different conflicting,

**Benjamin Goldfried** [00:43:45]

conflicting resources for Serval to look at, and then the second is specifically about audit logs.

**Benjamin Goldfried** [00:43:52]

So, as we're requesting access, and things are routed through access management, you can see here that it's very cleanly…

**Benjamin Goldfried** [00:44:00]

Mapped within these… audit logs over here. For…

**Benjamin Goldfried** [00:44:07]

requesting access to applications and that being approved or denied, etc, etc. If you just create a one-off workflow or a one-off skill, that does not come across as cleanly within your audit log, so it can be harder to pull that information, essentially, if you ever get audited or you have, like, certain compliance standards.

**Davison Chung** [00:44:25]

Yeah, and I think you can filter in that log by an access event type that will specifically only show you access. Yeah. One question we have with the group, would Catalyst be able to create a config file, for example, a VPN config file?

**Benjamin Goldfried** [00:44:41]

I guess, like, could you give me more information associated with what exactly you mean by that? Like, what is the exact use case here?

**Davison Chung** [00:44:50]

Yeah, and if you want to raise your hand, I'm happy to take you off mute if you want to ask in more detail.

**Davison Chung** [00:45:08]

Example here is, like, users traveling to other countries or working remotely to access on-prem devices.

**Benjamin Goldfried** [00:45:17]

So, yes, I think Catos can help. I'm not sure if this would fall under the realm of, like, access management, unless users are, like, specifically requesting access to the VPN itself.

**Benjamin Goldfried** [00:45:30]

But yeah, I mean, Catalyst can definitely help you come up with… with those files for you.

**Davison Chung** [00:45:38]

Right?

**Davison Chung** [00:45:40]

Any other questions folks have? We have, you know, happy to stay on the call if people do, but also happy to give people

**Davison Chung** [00:45:48]

Time back, if nothing else is top of mind.

**Davison Chung** [00:45:55]

Anything coming down the pipeline, Ben, that you're excited for, or on Access, or that people should be looking out for? Other than, obviously, Access reviews going general?

**Benjamin Goldfried** [00:46:04]

Yeah, so, as, like, a little tidbit, I'm not sure…

**Benjamin Goldfried** [00:46:10]

if people saw, but there's actually this reclamation policy now. So this is a newer feature that… that we're rolling out to customers, but essentially what it will allow you to do is, within Okta, or whatever your IDP is, you can go and you can…

**Benjamin Goldfried** [00:46:25]

configure…

**Benjamin Goldfried** [00:46:28]

a last login sync, so you can see here, under settings here, I have this last login sync, and what I can do within an application.

**Benjamin Goldfried** [00:46:36]

is set, like, a reclamation policy. So if somebody hasn't logged into an application after a certain amount of days, I can configure a policy to go and essentially revoke that user's access, and this is really useful for, like.

**Benjamin Goldfried** [00:46:50]

for license, reclamation specifically. So that's something that is currently in beta right now, but…

**Benjamin Goldfried** [00:46:58]

yeah, really excited for that to roll out to GA.

**Davison Chung** [00:47:04]

Awesome. Super cool.

**Davison Chung** [00:47:06]

Great, well, thank you all for joining. I don't see any other questions in the chat, so we'll give people 10 minutes back, but thank you all for joining, encourage you all, and hope to see you all at future sessions of, Serval School here. Have a great rest of your day. Thanks, Ben.

**Benjamin Goldfried** [00:47:19]

Take care, everyone. Yep, bye.


---

# Serval 104 - Knowledge, Analytics, & Campaigns

Transcript from the Zoom Events recording, speaker and timestamp per turn.

**Davison Chung** [00:00:00]

Hi, everyone. Welcome to Serval 104, focused on knowledge, analytics, and campaigns. This is a great session going over three pretty different modules, but all really interesting and useful in their own right. I'm Joe Maisueta, who's a member of our deployment strategy team, and is going to walk through all the content.

**Davison Chung** [00:00:19]

As with all of our sessions, we want to make this interactive, and we want this to be, something where we get all your questions answered, so please use the Q&A, use the chat, feel free to raise your hand if you have something more complex that's worth, you know, and we can take you off mute to go over that as well.

**Davison Chung** [00:00:33]

But just to give you a quick lay of the land on where we're at in our Serval School series, this is the fourth session of our Foundations, or 100 series courses. Hopefully you were able to join us for 101 through 103. If not, I would recommend going back and doing those.

**Davison Chung** [00:00:48]

And then later this week, tomorrow, we have 105, and then bi-weekly, we have our advanced series. So, yeah, just if you haven't seen some of those sessions, we definitely recommend going back and checking those out, either recorded or live next week. But with that, I'm going to hand it over to Swetha to go over the content.

**Swetha Mohandas** [00:01:09]

Thanks Davison.

**Swetha Mohandas** [00:01:11]

Okay. I wanted to start off by just going over the three modules that we'll be covering today in today's session. So I'm going to start off with knowledge and talk about how you can sync your external knowledge bases into Serval or even create native knowledge articles with Serval's native knowledge base as well.

**Swetha Mohandas** [00:01:28]

And then how you can scope them down to a team and add permissions on knowledge bases as well.

**Swetha Mohandas** [00:01:34]

And then I'll move on to analytics and show you our built in dashboards that we provide all of our customers with, as well as custom dashboards that you get. You can actually build through catalyst.

**Swetha Mohandas** [00:01:46]

And then, finally, I will end with Campaigns, which is a product that you can use to send messages or forms to your end users, instead of actually waiting for a ticket to come in. So you can also build this via Catalyst, or set it up manually through our Campaigns feature.

**Swetha Mohandas** [00:02:06]

So with knowledge high level, we have 2 different sources. You can either import your external knowledge into Serval, or you can use catalyst to actually create

**Swetha Mohandas** [00:02:17]

a knowledge base with Serval's native knowledge base, and I wanted to show you guys the differences there, and when you would use one versus the other, or how you could also use both.

**Swetha Mohandas** [00:02:29]

So to start off.

**Swetha Mohandas** [00:02:31]

This is our knowledge tab. And here you can actually manage all your different knowledge sources. So these are all of the built in external knowledge sources that we have.

**Swetha Mohandas** [00:02:40]

But if you have knowledge stored in a location that's not in this list, you can actually still create a custom knowledge ingestion with that specific application.

**Swetha Mohandas** [00:02:51]

A good example of this is GitHub. I know a lot of people store their knowledge in repos and GitHub, and if you have GitHub connected as an integration, you can actually just use Catalyst and create a workflow to pull in all the different articles, and

**Swetha Mohandas** [00:03:05]

pull it into Serval and store it there as well. So, you're not limited to the specific

**Swetha Mohandas** [00:03:11]

integrations at all.

**Swetha Mohandas** [00:03:14]

And with the knowledge sources that are connected, each of the knowledge sources have a few different settings that are important, so you can choose which knowledge sources are used for searching and syncing. Sometimes people have knowledge articles and knowledge sources

**Swetha Mohandas** [00:03:30]

only for their internal it team that it shouldn't be accessible for external people. So that's a time where you can turn off searching. But most of the time you'll want the knowledge base articles to be surfaced to your end users.

**Swetha Mohandas** [00:03:44]

And then enforce permissions is available in certain external integrations as well. With integrations like ServiceNow, Zendesk, Confluence, there are permissions that are set in the application level, and only certain people in ServiceNow can view certain articles.

**Swetha Mohandas** [00:04:00]

So if you turn on enforce permissions, all those permissions will be mimicked on the Serval side as well. So if they don't have access to a specific article, maybe it's like only available to managers and IC would never be able to request that information and get that information on the Serval side.

**Swetha Mohandas** [00:04:16]

So this will. This is a really cool feature that all of our customers use to actually maintain these permissions.

**Swetha Mohandas** [00:04:25]

And then we have the option to cite the document links.

**Swetha Mohandas** [00:04:29]

Yeah, if you guys have worked with Serval and you've seen how it responds with knowledge articles, you know that it'll actually summarize the article instead of actually sending the entire article to the end user. But usually people like the small summarization as well as a source so people can click on it for more information.

**Swetha Mohandas** [00:04:47]

And then here we also have the option to import your external knowledge into Serval's native knowledge base. This is usually used when people are doing migrations from one application to Serval. So people always migrate from like

**Swetha Mohandas** [00:05:02]

an ITSM like ServiceNow or Zendesk Serval, and this, with just one toggle, will actually pull in all your knowledge base articles, so you don't have to work on, like, recreating them on the Serval side.

**Swetha Mohandas** [00:05:14]

And then finally.

**Swetha Mohandas** [00:05:15]

a thing I'll touch on are suggestions. So, if there are gaps in your knowledge base, and the help desk agent is able to actually find those gaps.

**Swetha Mohandas** [00:05:26]

It can actually create new knowledge articles and write back to ServiceNow, or certain other applications as well. So instead of you guys having to, like, manually go and make those updates, you can actually just

**Swetha Mohandas** [00:05:39]

Toggle this on and have it update itself. And of course it won't automatically do that. It'll show you the suggestion and then you'll have to go through the publishing process.

**Swetha Mohandas** [00:05:47]

But it makes it a lot more convenient.

**Swetha Mohandas** [00:05:52]

Cool.

**Swetha Mohandas** [00:05:55]

And I also wanted to touch on, these ranking rules. So, this is just for managing different knowledge sources. So, sometimes if certain knowledge

**Swetha Mohandas** [00:06:09]

articles contain some information over the other, and you want to actually rank different knowledge sources. This is a good way to actually set up specific rules.

**Swetha Mohandas** [00:06:18]

To actually trigger those rankings. I know before, previously, people were using skills, and they were like, okay, like, if it's something with benefits, use Confluence over ServiceNow. But now you can actually just restrict and boost certain articles based on these specific rules. So this is.

**Swetha Mohandas** [00:06:38]

because more people were kind of coming to us with this use case, we were able to actually build it natively in Serval. And now you can set it up yourself.

**Davison Chung** [00:06:47]

Question from the group here. When we're importing knowledge from various sources, like Confluence or Google Drive, is Serval going to reformat or streamline the formatting, and organize those various articles for you, or is it just taking it as is?

**Swetha Mohandas** [00:07:02]

Yeah, it'll actually… if it's structured with, like, folders and subfolders, it will be able to actually recreate that exact

**Swetha Mohandas** [00:07:10]

structure in Circle's Native Knowledge Base.

**Davison Chung** [00:07:13]

Yeah, so…

**Swetha Mohandas** [00:07:16]

You can see that there's that structure, and

**Swetha Mohandas** [00:07:19]

With… the structure and service now is just mimicked in Serval as well.

**Davison Chung** [00:07:24]

Yeah. And so it'll it'll it'll be a one-to-one mirroring, it won't be a reformatted version or it won't do any sort of like cleaning on top of it.

**Davison Chung** [00:07:31]

Although…

**Davison Chung** [00:07:33]

I think you're about to talk about this. Native knowledge base might be a good alternative for what you're wanting to do here, which is helping streamline and organize knowledge bases.

**Davison Chung** [00:07:43]

So, I think we're gonna… about to touch on that, so good, good question.

**Swetha Mohandas** [00:07:49]

Yep. So here with the native knowledge base, if you're actually importing from an external knowledge base into Serval, you can choose exactly how you want it structured and formatted.

**Swetha Mohandas** [00:08:00]

So, it'll… it actually will recreate it exactly like your article is structured right now, in that exact format. But if you do want to make changes, and if you want to make modifications, this is actually a great way to

**Swetha Mohandas** [00:08:14]

set those up in the… and you can also create a custom workflow to actually restructure your knowledge in Serval as well. Like, maybe you don't like how it's structured in your external source, and you want to make that modification. It has access to all your documents and all your folders, so instead of you actually importing it in and then manually making those changes, when

**Swetha Mohandas** [00:08:33]

Catalyst actually builds that ingestion, it can just make that change for you.

**Swetha Mohandas** [00:08:39]

Yeah, I know.

**Davison Chung** [00:08:40]

I think that… I think that bears repeating, maybe. Just, like…

**Davison Chung** [00:08:43]

you know, I think the scenario here is basically, we have our knowledge base, it's in Confluence, it's in Google Drive, we want to import it into Serval, but we also want to take that as an opportunity to actually, like, streamline and organize our knowledge. What is your, sort of, like, end-to-end workflow, or sorry, end-to-end process for doing that transition?

**Swetha Mohandas** [00:09:02]

So this is if you want to reorganize or just keep the structure. I guess that's where I'm kind of a little confused on.

**Davison Chung** [00:09:09]

I think the point is like, let's say that I have a really messy, you know, knowledge base that's existing in Confluence and Google Drive, and I want to use this transition to Serval.

**Davison Chung** [00:09:18]

as an opportunity to not only, like, import all that knowledge, but also, like, clean it up at the same time, what would be your sort of, like, step-by-step process for transitioning knowledge into Serval in a way that not only replicates it, but also, like, improves it?

**Swetha Mohandas** [00:09:33]

Yeah, I think, yeah, that makes a lot more sense, actually. Okay, I will… let me touch on that.

**Swetha Mohandas** [00:09:39]

I was gonna talk about, like, real quick background agents and how to use that to actually clean up and restructure knowledge. So, after I go over this native knowledge base, I'll touch on that, and if there's still any open questions, then we'll get to those then.

**Swetha Mohandas** [00:09:52]

But yeah, amazing questions there.

**Swetha Mohandas** [00:09:56]

Okay, yeah, so another thing I wanted to touch on is with these knowledge articles in Serval's native knowledge base, we support versioning as well, very similar to how you see workflows and skills being versioned. You'll be able to see exactly who's made the update, when it was

**Swetha Mohandas** [00:10:11]

Published, who published it, and you can restore previous versions as well.

**Swetha Mohandas** [00:10:16]

And you can actually make sure this knowledge base also goes through the approval process similar to other sources.

**Swetha Mohandas** [00:10:25]

You can actually choose who has access.

**Swetha Mohandas** [00:10:28]

To see the page, and similar to the access profiles that you guys set up for

**Swetha Mohandas** [00:10:34]

roles and resources for access provisioning. You can actually set up those same access profiles here and have only certain folders or certain articles available to certain users.

**Swetha Mohandas** [00:10:45]

Since not everyone might need access to all of these articles. So similar to the permissioning you guys have in your external sources, you can add the same sort of granular permissions with Servable's native knowledge base as well.

**Swetha Mohandas** [00:11:01]

Awesome.

**Swetha Mohandas** [00:11:04]

Any questions there?

**Swetha Mohandas** [00:11:09]

Cool.

**Swetha Mohandas** [00:11:13]

Well, and then regarding the question about

**Swetha Mohandas** [00:11:16]

like, messy knowledge bases and how to use Serval to actually fix it and clean it up. We have this idea of background agents in Serval. If you guys actually haven't played around with background agents, I'd highly recommend going in and trying to create a few different background agents. We also have

**Swetha Mohandas** [00:11:34]

our agent library, which has a few installable background agents that you can start with and kind of understand how these agents work. But the idea is you can run these agents on a schedule of your choice, and you can use Catalyst to actually build it, and it can actually do almost any sort of action you need, like, it can

**Swetha Mohandas** [00:11:54]

look through your databases, it can look through your tickets, but what I wanted to show is this knowledge conflict scan.

**Swetha Mohandas** [00:12:02]

So what it does here is it actually looks through.

**Swetha Mohandas** [00:12:07]

It looks through your… all your knowledge bases on knowledge base articles and finds any conflicts or outdated resources.

**Swetha Mohandas** [00:12:15]

So, this runs…

**Swetha Mohandas** [00:12:18]

I think the one I created runs every week, but you can have it run in a monthly cadence or daily cadence, and

**Swetha Mohandas** [00:12:26]

Here, it was actually able to…

**Swetha Mohandas** [00:12:28]

Look and see, okay, there were…

**Swetha Mohandas** [00:12:31]

28 published articles and 42 are native articles. And here these are all the topics. These are the topics that have high impact and high conflicting documents.

**Swetha Mohandas** [00:12:43]

So it'll flag those and it'll tell you what actions to take there to actually fix these. And the cool part is you can actually.

**Swetha Mohandas** [00:12:52]

you can read this entire report, and it'll end up with recommended fixes. And instead of you having to actually go in and make these fixes, you can ask catalyst to

**Swetha Mohandas** [00:13:02]

Recreate these knowledge articles, or remove, certain knowledge articles and things like that as well.

**Swetha Mohandas** [00:13:09]

And with our native knowledge base, a cool thing we have, we can add owners to different articles and different folders as well. So what could be cool is you could create this background agent, and if there are issues with certain articles, you can make sure the agent will actually

**Swetha Mohandas** [00:13:26]

tag that individual, or send them a Slack message, or email, whatever their form of communication is, to actually inform them to go, take a look at this article and make these changes themselves, since

**Swetha Mohandas** [00:13:37]

You might not be the owner and might not have permissions to actually make those changes.

**Davison Chung** [00:13:43]

Yeah, absolutely. So just to zoom out and sort of

**Davison Chung** [00:13:46]

Just so I understand as well, the steps would basically be, if you're transitioning fully to a Serval native knowledge base from an external knowledge base, which is really powerful, because you can work with Catalyst and background agents in that knowledge base, the first step would be just to import all of your messy, you know, knowledge base articles just as they are, get them into Serval.

**Davison Chung** [00:14:06]

I think the next step then would be working with Catalyst to do that sort of like initial review, right? You can do all the cleaning with Catalyst. You can ask it this prompt of like, hey, help me clean up my knowledge base, help me find conflicts, help me reorganize or reformat, things like that, and actually make the changes. And so getting it to a clean state is something you can do collaboratively with Catalyst. And then on an ongoing basis, you can turn on this background agent.

**Davison Chung** [00:14:29]

basically proactively keeps your knowledge base clean.

**Davison Chung** [00:14:32]

And so, that would be sort of, like, the three-phase approach to how to go from your existing knowledge base to a Serval, clean, self-healing knowledge base.

**Swetha Mohandas** [00:14:41]

Yeah, for sure. Yeah, that is exactly the steps that I would recommend taking for this.

**Davison Chung** [00:14:47]

Cool. Yeah, I think really good, really good question. Let us know if that, if that gets to the heart of it, but I'll let Swetha get back to, the content.

**Swetha Mohandas** [00:14:56]

Yeah.

**Swetha Mohandas** [00:14:57]

Were there any questions with external knowledge, internal knowledge, or…

**Swetha Mohandas** [00:15:02]

Background agents for knowledge as well.

**Swetha Mohandas** [00:15:08]

Anything else that comes up top of mind?

**Davison Chung** [00:15:10]

I have a question.

**Davison Chung** [00:15:12]

I think that there's sometimes confusion between when would I create a new knowledge article versus when would I use a skill. Can you talk me through how you might think about those differently?

**Swetha Mohandas** [00:15:23]

Yeah, of course.

**Swetha Mohandas** [00:15:24]

So with a skill, I would actually recommend using that when you need to guide your helpdesk agent to behave a certain way and actually take actions in a certain way, not really just inform the user and give them like a one time response for a question.

**Swetha Mohandas** [00:15:43]

I know sometimes it can be, like, interchangeable, and a skill could be used to do that, but I would recommend really keeping that separation and only using skills for that instructional use for the help desk agent. So, a good example

**Swetha Mohandas** [00:15:58]

I always like to give with skills, is…

**Swetha Mohandas** [00:16:01]

My my laptop is slow, right? This. Yeah, you could have a knowledge article that actually gives them a step by step on how to resolve this. But if most of the time, like people connect their MDM and they actually have workflows built.

**Swetha Mohandas** [00:16:18]

to help with slow laptops. So that's where I would use a skill. And in a skill, you can actually run workflows. So skills and workflows collaborate really well together, whereas if you know there's no automation and, nothing end-to-end that you can automate, then that's where I would.

**Swetha Mohandas** [00:16:37]

go and fall back to a knowledge article that will just tell the user a step-by-step on what to do, or just give them an answer if it was… it's an easy question, like, what's my PTO policy? What's my Wi-Fi? Those are, like, straight answers that can be provided with knowledge.

**Swetha Mohandas** [00:16:52]

And there's no automations behind it. So that's when I would recommend using that.

**Davison Chung** [00:16:59]

Great, makes sense.

**Davison Chung** [00:17:01]

I don't see any other questions about knowledge right now. We can always return to it, but why don't we move on?

**Swetha Mohandas** [00:17:07]

Okay.

**Swetha Mohandas** [00:17:09]

Awesome.

**Swetha Mohandas** [00:17:11]

Next thing I wanted to touch on are analytics. So, if you guys have been

**Swetha Mohandas** [00:17:15]

our customers for a while, you probably realize, like, this page has changed a lot since you first joined. We've recently revamped our analytics to include a lot more, granular information for our

**Swetha Mohandas** [00:17:30]

initial dashboard that we give our users. So here, you're able to actually see.

**Swetha Mohandas** [00:17:37]

how the tickets are split up, and which ones are AI-resolved, AI-assisted, and the number of workflows that have run as well. So the difference between AI-resolved and AI-assisted… AI-resolved is end-to-end, the help desk agent is able to resolve the answer, whether that's, like, a knowledge-based article, running a workflow, and there's no human that

**Swetha Mohandas** [00:17:56]

Needs to step in and actually help on this ticket.

**Swetha Mohandas** [00:17:59]

AI assisted, on the other hand, could involve

**Swetha Mohandas** [00:18:03]

running workflows and giving answers with the automations you guys have built, but then it might need to escalate the ticket to a human for just, like, a further review, or just additional help on the ticket. So that's a good way to measure both those differences.

**Swetha Mohandas** [00:18:18]

And then,

**Swetha Mohandas** [00:18:21]

Yeah, so that's kind of the difference there. And then you can also take a look at the number of tickets that you're getting in, and how it's being resolved each day.

**Swetha Mohandas** [00:18:35]

And this is something that you can also.

**Swetha Mohandas** [00:18:38]

Switch the calendar view to, like, the past year, like…

**Swetha Mohandas** [00:18:43]

Or like even the past week if you're trying to just measure more short-term goals.

**Swetha Mohandas** [00:18:49]

And then this is a really important one that people like to see as well, just like time to resolution. You want to see that your tickets are getting resolved quicker, and you're able to provide your end users with support as quick as possible. So this is where you can also track that, and you can also track it by assignee.

**Swetha Mohandas** [00:19:06]

And then over here, we just have, like, the daily flow of tickets, like, how many are created, how many are closed.

**Swetha Mohandas** [00:19:12]

Things like that.

**Swetha Mohandas** [00:19:14]

And you can…

**Swetha Mohandas** [00:19:16]

also restructure this entire page, like, if you want certain widgets above others, and you want to remove certain ones, that's… it's all dynamic and customizable to you guys, so… Don't feel like you need to.

**Swetha Mohandas** [00:19:30]

Stick to the structure.

**Swetha Mohandas** [00:19:33]

And then the last two ones on this page are just feedback and SLAs. So once you guys have feedback and SLAs set up in settings, you can actually also track those here.

**Swetha Mohandas** [00:19:43]

And you can make sure if there's any breaches that you're able to see that immediately in your dashboards. And you can also create notifications or whatnot too.

**Swetha Mohandas** [00:19:54]

Notify users on this as well.

**Swetha Mohandas** [00:19:59]

And this page is just everything that we give to you guys out of the box with Serval, but a lot of the times, people really like their customized dashboards that they have, and they want

**Swetha Mohandas** [00:20:10]

certain dashboards for certain people. They also want the dashboards to have certain fields that are out-of-the-box dashboards might not support. So, you can actually use Catalyst to build out a dashboard on your own.

**Swetha Mohandas** [00:20:25]

So here, if you just go here, you can actually just see… this is just looking at all the devices in

**Swetha Mohandas** [00:20:33]

the database, and it actually builds out different graphs and different charts for you guys to actually analyze. And this is all done through Catalyst, so you can actually just

**Swetha Mohandas** [00:20:45]

give catalyst a prompt and it'll actually go through and create a dashboard there. So create a dashboard.

**Swetha Mohandas** [00:20:55]

to analyze… Check it.

**Swetha Mohandas** [00:20:59]

And…

**Swetha Mohandas** [00:21:11]

and then catalyst will just go through and

**Swetha Mohandas** [00:21:13]

Read all the different tickets that are coming in, and create

**Swetha Mohandas** [00:21:17]

a specific graph for you based on that as well.

**Davison Chung** [00:21:25]

While we're waiting on this, a question came up about knowledge-based background agents, and whether it only looks to the knowledge… the Serval native knowledge base, or it looks through all the accessible content for conflicts.

**Swetha Mohandas** [00:21:37]

So once you actually add Zendesk, for example, as a knowledge base, and it's ingested and synced into Serval.

**Swetha Mohandas** [00:21:46]

Your background agent can look through those articles as well and give you updates. So it's pretty cool.

**Davison Chung** [00:21:52]

Can it make those updates back into Zendesk?

**Swetha Mohandas** [00:21:56]

It depends on if

**Swetha Mohandas** [00:21:58]

I need to confirm if Zendesk is one of those that supports it. I don't think we have it here, but like I mentioned…

**Davison Chung** [00:22:05]

Then on the 3rd, yeah.

**Swetha Mohandas** [00:22:07]

It depends on, yeah, if Zendesk supports it, and if you toggle on this generate new knowledge toggle, then yes, you can…

**Swetha Mohandas** [00:22:14]

You'll get those suggestions, and you can just actually import those… export those suggestions back to Zendesk as well.

**Davison Chung** [00:22:21]

Yeah. Cool.

**Davison Chung** [00:22:23]

Sorry to interrupt.

**Swetha Mohandas** [00:22:25]

No, no, no, of course.

**Swetha Mohandas** [00:22:28]

Okay, cool. So here, I just gave it a super, super vague prompt, and I just said, analyze all the tickets, and then, the categories associated with it. And here, it was actually able to pull in all the different categories that we have set up, and break the tickets down.

**Swetha Mohandas** [00:22:44]

In, like, a table and a graph, which has been… which is pretty cool.

**Swetha Mohandas** [00:22:54]

Awesome.

**Swetha Mohandas** [00:22:58]

Any questions with analytics?

**Davison Chung** [00:23:04]

Can you just show again how you might build a dashboard that, you know, you want to prioritize for the whole team, and like, I think that that's a pretty common one.

**Swetha Mohandas** [00:23:14]

Oh, for the whole team?

**Davison Chung** [00:23:17]

Yeah, like let's say that I'm the team manager or or admin and I want everyone on the team to be looking at my customer dashboard. What's the easiest way to set that up from just a configuration standpoint?

**Swetha Mohandas** [00:23:31]

So is that with one specific dashboard, or just all the dashboards in general?

**Davison Chung** [00:23:36]

Yeah, like, let's say that I want a custom dashboard that I want my whole team to be looking at, like, the same version of, like, how do I… how do I make sure they're looking at that, or they have access to it?

**Swetha Mohandas** [00:23:47]

Yeah, you can actually… Go ahead and you can, like, add specific…

**Swetha Mohandas** [00:23:53]

You can add specific widgets here. You could also go here and pin dashboards to the sidebar.

**Swetha Mohandas** [00:24:00]

So, you can add different sections, you can pin specific dashboards, so if you want to have, like.

**Swetha Mohandas** [00:24:07]

It based on categories.

**Swetha Mohandas** [00:24:09]

Or exactly, like, just, like, one main dashboard that people need to have access to, you can add that as well.

**Davison Chung** [00:24:17]

Cool. Makes sense.

**Swetha Mohandas** [00:24:18]

Does that answer the question?

**Davison Chung** [00:24:20]

Yeah, yeah.

**Swetha Mohandas** [00:24:20]

Okay, cool.

**Davison Chung** [00:24:21]

And then there's another question here.

**Davison Chung** [00:24:24]

From one of the dashboard gadgets, when clicking on it, would allow me to view all the tickets it uses. I think… oh, yeah, so I think this is a question about, can you double-click into Into dashboards and see the underlying tickets or assets or whatever else.

**Swetha Mohandas** [00:24:39]

I believe that's something that we are currently working on or should be feature flagged.

**Swetha Mohandas** [00:24:46]

So, I will get back to you guys on when we will be able to…

**Swetha Mohandas** [00:24:53]

I'm trying to see if there's…

**Davison Chung** [00:24:55]

Yeah, I believe Ava is working on this, and it's, it's, it's, it's on the, it's on the to-do.

**Swetha Mohandas** [00:25:01]

Oh, there we go, yeah, so it…

**Davison Chung** [00:25:02]

There you go.

**Swetha Mohandas** [00:25:04]

I was like, it's either almost done or done. But yeah, you're a once you click it.

**Swetha Mohandas** [00:25:10]

into this. If there are tickets associated with it, you can go ahead and take a look and look into the ticket itself.

**Davison Chung** [00:25:15]

Yeah, that might be something that isn't available yet for general use, but it is something that we're building, and you can see the first version of it here.

**Swetha Mohandas** [00:25:23]

Yeah.

**Davison Chung** [00:25:25]

There was a question, I think, generally around, like, knowledge articles and how to create knowledge articles, and so, is there a way to review responses on historic Zendesk tickets to create SOPs and knowledge articles? you know, replace Zendesk with whatever, previous ITSM.

**Swetha Mohandas** [00:25:44]

So, is there a way to…

**Swetha Mohandas** [00:25:46]

Sorry, could you repeat the question?

**Davison Chung** [00:25:48]

Yeah, could we download or sync in historic.

**Davison Chung** [00:25:53]

Tickets, and how they were responded to, and how they were resolved.

**Swetha Mohandas** [00:25:57]

forward.

**Davison Chung** [00:25:57]

build new SOPs and knowledge articles.

**Swetha Mohandas** [00:26:00]

Yes, of course. So, even when we're piloting and going through deployment with a lot of our customers.

**Swetha Mohandas** [00:26:07]

A lot of our customers like to actually give us their ticket data, and what you can do is actually just upload it to Catalyst.

**Swetha Mohandas** [00:26:13]

And you can actually take a look at, one, all the different ticket categories, and then you can actually ask it to scrape through all the tickets, and and if you also have your knowledge ingested, you can actually just tell it to, like.

**Swetha Mohandas** [00:26:26]

look at the gaps and compare the gaps between what knowledge we have and what was not answered, and because if the question wasn't answered, some human must have stepped in to actually resolve the ticket. So, you can actually pull in all that information and ask it to generate new knowledge articles, and you won't have to do anything manual, like, Catalyst will be able to do that.

**Swetha Mohandas** [00:26:46]

for you.

**Davison Chung** [00:26:47]

Yeah, definitely. And then, you know, another really good use for

**Davison Chung** [00:26:51]

You know, this is native in suggestions, which is, you can find in workflows as well as in skills, but suggestions will tell you, on a recurring basis, what are the questions that we are not resolving automatically, and how could we build workflows or skills that address those gaps. And so both

**Davison Chung** [00:27:10]

looking back at your historicals, but also looking at your ongoing instance and figuring out how to continue to make it better. For knowledge, going back to knowledge, is there a feature for folks to be able to comment on articles?

**Swetha Mohandas** [00:27:24]

Hmm.

**Davison Chung** [00:27:25]

With regards, I assume, to like collaboration internally.

**Swetha Mohandas** [00:27:29]

Yeah.

**Swetha Mohandas** [00:27:30]

And I'm assuming this is like specifically with native knowledge.

**Swetha Mohandas** [00:27:36]

We don't allow comments today.

**Swetha Mohandas** [00:27:39]

But we do have… like a publishing flow. So if you add approvers to

**Swetha Mohandas** [00:27:48]

a specific… like, if you had specific approvers to approve, like, workflows or skills or knowledge, then you can actually, like, add a, like, comment and description explaining, like, what your changes are.

**Swetha Mohandas** [00:28:01]

But right now, we don't have that, like.

**Swetha Mohandas** [00:28:03]

like something similar to Github, with like comments back and forth. But that is something we're looking to eventually also support.

**Davison Chung** [00:28:11]

Yeah, good question.

**Davison Chung** [00:28:16]

Okay, any other questions about knowledge or analytics?

**Davison Chung** [00:28:22]

I think custom… I'll just put another plug for custom dashboards. I think probably an underrated feature, because it is super, super customizable. You don't have to just talk about tickets, you can talk about really, like, any data that you've connected into Serval, and Patos will be able to build you these dashboards on the fly.

**Davison Chung** [00:28:39]

Directly from whatever you've connected in. And so, definitely worth, sort of.

**Davison Chung** [00:28:43]

playing around with, brainstorming, thinking about, okay, what does Serval actually have access to, and what would I want reported on there, and sort of going outside the lens of just, like, your standard ticketing views.

**Swetha Mohandas** [00:28:54]

Yeah.

**Davison Chung** [00:28:59]

Cool. Should we move on to Campaigns?

**Swetha Mohandas** [00:29:01]

Yep. Let's do it.

**Swetha Mohandas** [00:29:03]

Okay, just wanted to quickly touch on this slide, which shows a high-level overview of how Campaigns work.

**Swetha Mohandas** [00:29:10]

So there's like five main steps to setting up a campaign. You'll need to like name the campaign, choose the channel it goes through, pick who's receiving this campaign and in what schedule they're going to receive it and what you're actually sending to them, whether that is.

**Swetha Mohandas** [00:29:25]

Workflow, or… A one-time message, or a workflow to actually collect information via a form.

**Swetha Mohandas** [00:29:34]

So I just wanted to, like, go through the process of how you can set up that campaign.

**Swetha Mohandas** [00:29:39]

So if you go here and actually the first step, like similar to the five steps I laid out, you'll just need to name the campaign.

**Swetha Mohandas** [00:29:56]

And then you can add a description as well here.

**Swetha Mohandas** [00:30:00]

And then we have a few different.

**Swetha Mohandas** [00:30:03]

different places where you can actually send this campaign to. So you can send it to

**Swetha Mohandas** [00:30:10]

Slack or Teams DM, we see email also as a popular option, and this… the embedded widget is a newer option that we've just recently supported as well.

**Swetha Mohandas** [00:30:20]

And you can also choose exactly who's going to receive this campaign. So this can be specific users, specific groups that you're pulling in.

**Swetha Mohandas** [00:30:29]

You can also upload a CSV with all the different users and all the different fields that you want to pull in from the CSV, or you can actually use a workflow to pull in users, maybe if it's from a database or, from a different application, so things like that.

**Swetha Mohandas** [00:30:48]

So here I'll just add Davison

**Swetha Mohandas** [00:30:55]

And then I'll allow myself.

**Swetha Mohandas** [00:31:00]

And then here, there's 3 different ways you can actually send this campaign out. It can either run immediately, you can schedule it for a later time, and you can choose the exact time zone, and… or you can actually schedule it specifically for the recipient's time, so it'll…

**Swetha Mohandas** [00:31:18]

deliver at 4pm for everyone in their respective time zones.

**Swetha Mohandas** [00:31:21]

And you can either make this one time or reoccurring, which we've seen a lot of people do as well, or create a specific trigger and only when that trigger hits.

**Swetha Mohandas** [00:31:32]

And you can create this as, like, a workflow trigger, and only when that trigger hits, the campaign will be sent.

**Swetha Mohandas** [00:31:39]

And a good… kind of… Example of using a trigger is.

**Swetha Mohandas** [00:31:45]

We see a lot of people use Campaigns for laptop refreshes. So if their laptop is older than two years, then it'll actually

**Swetha Mohandas** [00:31:54]

like, every… it's actually, like, a scheduled workflow that's running and checking this, and if any of these laptops, like, are affected and are older than 2 years, then it'll actually run this campaign and send it to those specific individuals, so…

**Swetha Mohandas** [00:32:06]

That's kind of the use case there.

**Swetha Mohandas** [00:32:09]

Cool. And here, let's just make this a one-time pane.

**Swetha Mohandas** [00:32:14]

And then here, this is where you can actually pull in different variables, since we're just

**Swetha Mohandas** [00:32:19]

Selecting specific users, these are the, like.

**Swetha Mohandas** [00:32:23]

the very basic variables that are being pulled in. But if you upload a Csv, and you want to include other information about these specific individuals, you can actually pull those in as well. So I can just say, Hi.

**Swetha Mohandas** [00:32:43]

2 days.

**Swetha Mohandas** [00:32:46]

And then here, you can actually,

**Swetha Mohandas** [00:32:50]

you can actually just send a specific workflow and create a specific workflow that you want to pull in information from. So here I just have, like, a very basic feedback workflow that will just actually have a few input fields and then store those on our side.

**Swetha Mohandas** [00:33:06]

And what's cool is you can actually send previews

**Swetha Mohandas** [00:33:09]

Of the campaign, so if you want to make sure the form is exactly like you expect it to be, you can actually send a preview to yourself.

**Swetha Mohandas** [00:33:17]

And just test it out before you actually send it to others.

**Swetha Mohandas** [00:33:21]

So that's… Pretty cool as well.

**Swetha Mohandas** [00:33:26]

And then finally, you can review this campaign, and then save it.

**Swetha Mohandas** [00:33:31]

And then once you hit publish, This will actually go to…

**Swetha Mohandas** [00:33:37]

both Davison and I, and then we can actually go to Slack and fill out that specific campaign.

**Swetha Mohandas** [00:33:45]

This… the feedback.

**Swetha Mohandas** [00:33:49]

And then once… Once the users fill it out, you can actually track all the responses here.

**Swetha Mohandas** [00:33:56]

And I can even go ahead and show another campaign that has some more responses. So you guys can see the end view.

**Swetha Mohandas** [00:34:10]

So here, for our…

**Swetha Mohandas** [00:34:12]

quarter off-site, we always use Campaigns to figure out, what activities people want to do, so here you can actually go track which one they want to attend, and which day works for them, and then, track all the responses here. You can track who actually hasn't responded or hasn't submitted it.

**Swetha Mohandas** [00:34:30]

and then the configuration you've set up as well. You can track all those things here.

**Swetha Mohandas** [00:34:35]

And what's cool is…

**Swetha Mohandas** [00:34:36]

Catalyst has full access to all this information and all this data, so you can actually use it to maybe update the database or, create workflows depending on the output that you get from a campaign as well.

**Swetha Mohandas** [00:34:54]

And then I showed you guys, like, a form example of a campaign, but a lot of times when customers are rolling out with Serval.

**Swetha Mohandas** [00:35:02]

It's pretty cool that they use Campaigns to actually send comms out to their end users about Serval. So, they'll get a DM to the Serval app, and it'll tell them, like, hey, like, you can come here with any questions you might have, you can go to this channel for IT questions, this…

**Swetha Mohandas** [00:35:16]

other channel for HR questions, or use the Serval app on Slack or Teams, so… It's a good…

**Swetha Mohandas** [00:35:25]

Use case to actually… like, send your 1st campaign and have it low pressure as well.

**Davison Chung** [00:35:32]

Totally.

**Davison Chung** [00:35:33]

Do you have any, like, other… fun or useful use cases for campaigns that you see people rolling out with? I think there's obviously a lot of flexibility, and depending on the team that's using this and things like that, but yeah, any that come to mind.

**Swetha Mohandas** [00:35:48]

Recently, like, one of my customers that just went live, they were trying to…

**Swetha Mohandas** [00:35:52]

figure out what to call their Slack app, and what, what, like, emoji, not emoji, what image to use for it as well. So, internally, with the team that we were working with, like, we were working with their HR and IT team, so they sent a campaign to the team with all the different, like.

**Swetha Mohandas** [00:36:10]

name options as well as all the different icons. So then that's how they actually ended up picking how their Slack app was going to look for production. So it was kind of cool and it was like a fun way for them to use Campaigns and they had a lot of fun building it as well.

**Swetha Mohandas** [00:36:24]

And also on regards to building it, you can actually build campaigns using Catalyst now as well. So.

**Davison Chung** [00:36:31]

Super cool. Question from the group. Is the text in the campaign in Markdown?

**Swetha Mohandas** [00:36:38]

I believe you can set it up in Markdown.

**Swetha Mohandas** [00:36:42]

I will confirm… I'll I'll confirm that.

**Swetha Mohandas** [00:36:46]

Real quick, but I believe that is supported.

**Davison Chung** [00:36:53]

Cool.

**Davison Chung** [00:36:54]

Great. Well, I think that that's all the content that we had planned. We do have 20 minutes left here, and so we'll open it up to the group for any additional questions people have about knowledge, analytics, campaigns, anything else that's top of mind or that has come to mind while you've been watching this session with regards to Serval, we're happy to stick around and answer questions.

**Davison Chung** [00:37:12]

While you all are thinking of your final questions, I'll just give one final plug for the rest of the sessions we have this week, and going on in Serval School in general. So, later this afternoon, we have a session on journeys, which we'll dive into. The most common use case, which is employee joiner, mover, lever flows, onboarding off-boarded, but can be used for any sort of cross-team.

**Davison Chung** [00:37:35]

Segmented, different, you know, multiple owner type process.

**Davison Chung** [00:37:39]

like that. And then tomorrow we have our 105 session that's focused on governance teams and permissions, which is going to be more of an admin level or manager level session, talking about, again, governance and how you set up your, your instance to accommodate all the different people who will be using it, in the, in the most, kind of, best practice manner.

**Davison Chung** [00:37:59]

All of this is rolling up as part of Serval School and our Serval Certified program. So, to get Serval Certified, which we just launched about a week, week and a half ago, what you have to do is attend these webinars, both the 100, 200 series, 8 in total. Once you do that.

**Davison Chung** [00:38:16]

We will shoot you an email and you will be eligible to take the credentialing exam, certification exam. That's 50 questions, multiple choice, takes about 30 to 45 minutes depending. And if you pass, you will get your official credential through our partners at Accredible.

**Davison Chung** [00:38:32]

And so that's the process. I'm gonna put my email in the chat in case anyone has questions about that, or if questions come up as people are going through the webinars. And I'm going to share the Serval School landing page as well.

**Davison Chung** [00:38:48]

Which is right here, which is where you can register for live webinars, you can watch or revisit, past webinars, on demand, as well as has the sort of basic requirements around Circle Certified.

**Davison Chung** [00:39:01]

There is not currently a landing page to show the events that we attended. We don't have

**Davison Chung** [00:39:06]

that right now, but again, you can always reach out to me, Davison at Serval.com. We're just… we're monitoring attendance based on people who register and who attend events on the email, and so just make sure you're using the same email to go to these events. Or if you're having an issue, please just shoot me an email. Would love any and all feedback, and appreciate people's patience as we are just ramping this up and getting better.

**Davison Chung** [00:39:30]

Day over day with it, so…

**Davison Chung** [00:39:32]

That's all I had. I don't see any other… oh, sorry, go ahead.

**Swetha Mohandas** [00:39:36]

Yeah, sorry, just for the markdown, we actually use tip-tap JSON instead of markdown.

**Swetha Mohandas** [00:39:42]

So, yeah, we… that's… that's what we support.

**Davison Chung** [00:39:48]

Gotcha. Cool. Thanks for the clarification.

**Davison Chung** [00:39:51]

But yeah, I don't see any other questions. Thank you for joining us. I hope to see people at future sessions.

**Davison Chung** [00:39:58]

And yeah, feel free to reach out to us at jamesonaturville.com if you have any questions about this session or any other sessions you have.

**Davison Chung** [00:40:06]

Yes, and once you attend all the sessions, you will get your invitation from me, and if you feel like you've not gotten your invitation and you deserve one, please shoot me an email. But yes.


---

# Serval 105 - Governance, Permissions, & Teams

Transcript from the Zoom Events recording, speaker and timestamp per turn.

**Davison Chung** [00:00:00]

Hey everyone, happy Friday. Thank you for joining us for Serval 105, the last session in our 100 series, our Foundation series, focused on governance, permissions, and teams.

**Davison Chung** [00:00:13]

I'm joined by Derek, who's on our deployed software engineering team. Derek is gonna run you through all the content, but excited to dive into this. As with all the sessions, please, let's make it interactive. I want to see questions in the chat, I want to see questions in Q&A. Feel free to raise your hand if you have something specific to call out. But with that, I'm going to hand it over to Derek to get us started.

**Derek Zheng** [00:00:37]

Awesome. Thank you, Davison.

**Derek Zheng** [00:00:41]

I'll be flipping between a series of visuals, as well as kind of jumping into the product to walk through kind of what we want to, talk about today. At a high level, we'll start with permissions and kind of the basics of

**Derek Zheng** [00:00:56]

how Serval's structured and functions, and then we can walk into development lifecycle, and then finally get into some recommendations that we generally share with people. Of course, at any point, you know, you might have a unique situation, and this is just broad guidance, so,

**Derek Zheng** [00:01:14]

please, please check with, you know, your contact at Serval to ensure that, you know, the direction you're thinking makes sense for your situation.

**Derek Zheng** [00:01:26]

Alright.

**Derek Zheng** [00:01:28]

We'll jump over to these slides, and first, as I mentioned, I do want to cover how the permissions model in Serval just functions

**Derek Zheng** [00:01:39]

at the most basic level, and then talk about, kind of, the rest of the best practices here. Firstly, when we talk about permissions, we have a two-tiered structure of authority in Serval. What this means is there is organization-level controls, as well as workspace-level controls.

**Derek Zheng** [00:01:56]

That means that as a platform owner, you can administer the organization separate from individual workspaces, which generally correspond to departments, and

**Derek Zheng** [00:02:04]

I'll walk through a few more examples as we get through this presentation, but I think that's the most important framing for the different tiers and sides of the product as it relates to Serval. And so, when we're talking about the organization level, that, like, top-level platform and administration, there are three levels of roles that a user might have. The first one is org admin, the second is org member, and the third is org guest.

**Derek Zheng** [00:02:28]

They're increasing in terms of importance and power, so the org admin is really the owner of the product, right? Like, they can set and configure pretty much everything in the organization level.

**Derek Zheng** [00:02:40]

The org member is going to be your average employee, and so this person is going to be able to interact and log into the organization.

**Derek Zheng** [00:02:48]

you know, open requests and kind of get help from Serval, but they're not going to be able to administer or see the kind of settings and configurations behind the product.

**Derek Zheng** [00:02:57]

The last one is org guest, which is a kind of lower permission barrier. So, of course, with org admins and members, there is a level of trust with these different roles in that, you know, you're a part of the organization, or you're a part of the company at Serval, and you should be able to, you know, do a few basic things that

**Derek Zheng** [00:03:15]

Pertain to your daily job, to get help, to, you know, run through some automations.

**Derek Zheng** [00:03:20]

And org guests are going to be that bucket of external users, maybe they're contractors, maybe they're temporary employees, maybe they're employees who have just left the company, or are about to join the company, who aren't kind of full-time

**Derek Zheng** [00:03:33]

in the system, they don't have full access, but, you know, they still might have to ask questions or get help, and open tickets, and so that's kind of what the org guest policy is for. And so, again, just to reiterate, at the top level, this top-level organization, we have these three roles. There's going to be a very small number of org admins. Most employees at your company are going to be org members.

**Derek Zheng** [00:03:53]

And then org guests are going to be that external permission.

**Derek Zheng** [00:03:58]

Now, I can talk about a little bit of the identity model, right? So, the process of signing in and setting up all those different controls. To do so, I'm going to jump into the product here and come to the organization tab. In the organization workspace, I've come to the settings page, and this is what's really going to let me view things like the ability to

**Derek Zheng** [00:04:21]

You know, promote, demote certain users, the ability to, kind of set up these security controls.

**Derek Zheng** [00:04:30]

Give me one second…

**Derek Zheng** [00:04:36]

I'm gonna reshare my screen. Apologies.

**Derek Zheng** [00:04:42]

So here you'll see that same kind of…

**Derek Zheng** [00:04:44]

org-level permission structure of admins, members, and guests is something that I can, as an org admin in this Serval organization, view myself. So I can filter, I can search for specific users, I can promote them, I can demote them, I can remove them manually, if that's the preference.

**Derek Zheng** [00:04:59]

But generally speaking, most companies are going to have SSO and SCIM and other types of things set up

**Derek Zheng** [00:05:05]

to do provisioning and control provisioning in the way that kind of fits in their overall company policy. And so, here you'll see in the security section of organization settings, as an admin, I can come in and say, hey, you know, let me view the SSO configuration.

**Derek Zheng** [00:05:20]

I can verify my domain, I can configure SSO, I can enforce SSO as well, which essentially gates who can log into the organization.

**Derek Zheng** [00:05:28]

And additionally, I can also use SCIM, or configure SCIM, and set up groups that might be pushed to Serval from, you know, our provider WorkOS, or directly provision users and set their attributes to specific roles, such as the org admin and org member roles. And so you'll see here, when you kind of,

**Derek Zheng** [00:05:48]

come to the SCIM configuration portal, you'll be able to come to our provider, WorkOS, and do things like attach and assign roles, set up users and groups, as they're kind of

**Derek Zheng** [00:06:01]

set up in the product here. And so that's the primary way that I see people set up things like login, as well as configuring who's a user and what level of permission in the company. And so, of course.

**Derek Zheng** [00:06:13]

you know, you might see a case where Serval can automatically provision or add people to these different configurations, so that it can almost automate some of this for you.

**Derek Zheng** [00:06:23]

Now, I think while I'm on this page, I want to call out a few other important settings that live in the product, and so first is the concept of these team workspaces. So workspaces, I will call… I will talk about soon in terms of roles and kind of what they're designed to do, but as an org administrator, you're able to come review all the different workspaces.

**Derek Zheng** [00:06:45]

Manage whether, you know, tickets can be automatically routed to a team workspace or not. Identify team membership.

**Derek Zheng** [00:06:53]

What's most important to know about this is

**Derek Zheng** [00:06:55]

As an org admin, I'm actually not part of all these workspaces. These workspaces have their own individual kind of tier, as I mentioned, of permissions. They're completely segmented from the administration of the platform itself. And I'll get to a reason why that's the case, but as an org admin, you can also create new team workspaces and kind of configure this depending on which departments and, you know, internal groups, let's say, are

**Derek Zheng** [00:07:19]

going to be working in Serval.

**Derek Zheng** [00:07:22]

Other quick things that you can do as an org admin, you know, group membership, different groups, the different sources that they're synced in from. So if you have external systems, like, you know, an Okta, a Microsoft Graph, or Google, those things will populate here. You're also able to set up org API keys, so the ability to, you know, give specific credentials to take on specific actions in external systems.

**Derek Zheng** [00:07:44]

You can also, set up things like branding, so the thing, that a lot of people do is name their Serval, so if you wanted to customize all of that, that's something you can do from an administrative perspective as well. And then also the, kind of, new request portal, so the ability to, show, kind of, which cards show up on the main

**Derek Zheng** [00:08:03]

View in the organization when users log in to get help.

**Derek Zheng** [00:08:10]

Also, really importantly, there's a concept of audit logs, so the ability to set up, you know, who can

**Derek Zheng** [00:08:16]

I guess pull audit logs of specific actions across the organization, export these, download them to external sources.

**Derek Zheng** [00:08:26]

Just jumping back here at the org level, I've kind of covered the SSO, the SCIM, the connected application side. I also wanted to talk about the domain allow list, which sits in security as well, just at the bottom here. So what domain and Allow List allows you to do is essentially set up

**Derek Zheng** [00:08:42]

who, you know, specific rules on who can even become a user in Serval, who can even request things of Serval, so when we're talking about, you know, maybe interfacing with external users, or even if there's external users in your IDP that are getting synced over automatically, you can set up an additional layer of permissions and guardrails around who specifically can actually be that member or user in the platform.

**Derek Zheng** [00:09:05]

Of Serval, and so these are obviously really important things to to call out.

**Davison Chung** [00:09:12]

I have a question from the group here around, SCIM and user attributes. So, let's say that they have both a primary and a secondary email. How would they… how should they configure that on a user within Serval?

**Davison Chung** [00:09:25]

And have both of those attributes sync over.

**Derek Zheng** [00:09:28]

It's a great question. So, in Serval, we can…

**Derek Zheng** [00:09:31]

take in a primary email, but also in the SCIM configuration, you're able to map any number of additional emails, and so what Serval will do is, associate that to the same user object, and so if you had, you know, alternate email, that could be something you configure right within, the SCIM configuration here. So,

**Derek Zheng** [00:09:48]

you know, specifics will depend on what system that you're using to talk to Serval, but, you would be able to…

**Derek Zheng** [00:09:57]

in the mapping configuration that I don't have ready here, essentially associate, you know, Derek's primary email is derek at Serval.com, but then he also has a secondary email, which should be associated to his identity.

**Davison Chung** [00:10:14]

Cool. Thanks, Derek.

**Derek Zheng** [00:10:19]

Awesome.

**Derek Zheng** [00:10:21]

So, now I want to talk about workspaces. And so, team workspaces are a really important concept where, you know, you have the organization level controls, but there's also a series of workspaces that, can contain, you know, important work that stretches across the different departments in your organization. And so.

**Derek Zheng** [00:10:39]

typically what I see, from a Serval deployment is that we work with many different internal departments, many different internal teams who are, you know, taking on different types of work, and so what workspaces allow you to do is create these kind of hard, air-gapped boundaries around

**Derek Zheng** [00:10:54]

these, like, self-administering groups. And what I mean by that is, you know, IT's processes, IT's automations are kind of largely its own, and owned by its own users, but then, you know, HR, finance, legal, engineering, security, they all have separate concerns, and so these workspaces provide these

**Derek Zheng** [00:11:13]

kind of, I guess, like, sub-organizations in some way, where you can have contained units of, you know, organization, where you can self-administer and build exactly what you want to do. And so, in an IT workspace, you might do all the IT requests, automations, have all those connections living in that system. In the HR workspace, you might have a completely separate process of requests, processes, knowledge.

**Derek Zheng** [00:11:36]

And so, the most important thing is that

**Derek Zheng** [00:11:38]

That you all understand that, like, of all the different primitives and automations that you can build and Serval that you've been learning about in this builder webinar, that all of these belong to one workspace, and so they're owned at the workspace level. That workspace is a hard boundary that doesn't get shared between IT and HR, and so that preserves, kind of, separation of interests in a way.

**Derek Zheng** [00:11:59]

Now, within the workspace, you're able to, in each workspace, set up a series of permissions. So we have role-based access controls for who is in that workspace, and again, this is kind of that second tier of permissions, as I called out. So, separate from the organization, I can also have roles and individual workspaces.

**Derek Zheng** [00:12:16]

The roles in individual workspaces span from read-only agent, which is the most restrictive, to manager, which is almost kind of the administrator of that workspace. And so they're increasing in terms of power to build, to publish, to configure different settings in that workspace.

**Derek Zheng** [00:12:32]

And what you're also able to do is set up custom roles, which I'll also show soon in the product, where you can kind of pick one of these base roles that we have in the product, and then kind of customize it exactly to whatever your organization policy is, or whatever that person's role

**Derek Zheng** [00:12:45]

really entails. And so, with these custom roles, as I mentioned, we'll want to pick one of those base roles, maybe read on the agent, and then grant optional actions on top of that, depending on what you deem to be important. And then you can then associate those roles to different people, on the team, and that will allow you to kind of ensure that the people who are building stuff in those workspaces have the right level of permission, that you could scope that down to kind of, like, minimal permissions.

**Derek Zheng** [00:13:10]

So, to kind of demonstrate some of this to you, I'll jump into my IT team dev, excuse me, workspace, and I'll hop over to settings. So, similar to how I was in organization settings, I can have settings at each workspace. The first page that you'll see here is all of the users.

**Derek Zheng** [00:13:27]

And the users here have different roles, right? And so you can see that, you know, for, you know, Ashna in this case, I can pick one of these built-in roles, whether that's read-only agent, or manager, or something in the middle, as well as pick specific custom roles that we've defined on top of that.

**Derek Zheng** [00:13:42]

In addition, while I can manually assign some of this, I can also have groups. And so you can see here that, I have a push group from Okta that actually was configured in, kind of that skin configuration. That group has been ingested by Serval. That group is now associated to the demoer's role in this workspace. So everyone who's in the All Serval employees group

**Derek Zheng** [00:14:04]

in the product is now able to have that demo's role in the workspace, and so you can see how, you know, you might create groups called, you know, IT Manager, or IT Contributor, or IT, you know, special function.

**Derek Zheng** [00:14:16]

And associate those groups to specific roles here, and that will allow you to, again.

**Derek Zheng** [00:14:21]

Control the automatic provisioning and assignment of users to certain levels of privilege in that team.

**Derek Zheng** [00:14:27]

And so, again, I want to make sure that this difference is clear. So, you can see in both pages, they function pretty similarly. At the org level, I can view a list of users, I can assign those three roles, the admin, member, and guest, and then in each workspace, I can associate, you know, different roles that make sense to users. The most important thing and common confusion is, you know, the question of, do

**Derek Zheng** [00:14:49]

Any, you know, do employees need to be in these workspaces? And the answer is no.

**Derek Zheng** [00:14:54]

These workspaces allow you to kind of see the backend configuration or the admin-side configuration of the product, so the ability to even see tickets, the ability to, you know, work on tickets and respond to them, to run workflows, to build workflows, to, you know, administer the workspace itself. That all is kind of

**Derek Zheng** [00:15:11]

Kind of restricted to a set of people who you define here, but that's not going to span the entire, kind of,

**Derek Zheng** [00:15:18]

company, and so end user will still be able to interact with this team by submitting requests. Serval will be using what you have built there to create tickets in this workspace, to answer and use automations to help automate things. But most importantly, I want to make sure that point is clear, kind of that two-tiered structure, so

**Derek Zheng** [00:15:36]

Just to give a few anecdotes, I might be an org admin.

**Derek Zheng** [00:15:40]

And let's say I'm in the engineering department. I might have a role in the engineering workspace, but I might not have a role in any other

**Derek Zheng** [00:15:47]

workspaces internally. I won't be in HR, I won't be in IT, just because it's not appropriate based on my role, but sometimes, you know, I might be a non-admin, so a non-platform owner, but I also could be a manager or an administrator of the HR workspace. It's important for me to have control over what my workspace does, the settings, the different policies that Serval's following just for my workspace. And so you'll see a mix of, basically, that org-level role.

**Derek Zheng** [00:16:11]

And then those team workspace roles, were relevant.

**Derek Zheng** [00:16:18]

Awesome. So, within the workspace, I think there's a few other controls I want to quickly talk about. First is on ticket visibility, so,

**Derek Zheng** [00:16:27]

I guess before I get into that, I'll call out this framing that I like, which is, when you define an organization different workspaces, you're kind of creating these air-gapped environments, these walled gardens, so to speak. These workspaces, by default, are kind of hard-blocked from accessing each other's information. Of course, you can share things across those workspaces, and I'll get into exactly how that happens, but

**Derek Zheng** [00:16:50]

Really, these workspaces, you can use role-based access controls first to scope who can do what in those workspaces, but sometimes you still want to put up, you know, boundaries within the HR workspace, for example, where, you know, half the tickets are visible by, you know, only half that workspace of those workspace members, and the other half is visible by a separate group of people.

**Derek Zheng** [00:17:11]

And that's really important, obviously, just depending on the different policies and sensitivity that you have in that workspace, but I like that framing in terms of, like, when you define these workspaces at the org level, these are hard boundaries.

**Derek Zheng** [00:17:25]

And then within the workspaces, you can kind of set up additional walls, but it's more of an opt-in process. So again, workspaces are, like, where you opt out, or you break down the walls between workspaces. Within a workspace, you can put up walls, and so that… that framing usually helps people understand, kind of, for their organization, what makes sense for them, how to attack the workspace and permission model.

**Derek Zheng** [00:17:47]

So quickly, you know, what are those different walls you can put up within that workspace? The first one is ticket visibility, so the ability to say, you know, the first quarter of tickets should only go to, you know, Davison that is, like, super sensitive. He's the only one who should be able to view that. That's the type of rule that you can set up with assignment.

**Derek Zheng** [00:18:04]

With, with, sorry, ticket visibility.

**Derek Zheng** [00:18:07]

The second is, database, access controls, and so you might see in the databases product the ability to scope exact tables of, you know, data to specific groups or users, to share that with external teams. That is also a control that you can set up within that workspace.

**Derek Zheng** [00:18:24]

The other thing is on, kind of, this general, like, Workflow Builder.

**Derek Zheng** [00:18:30]

access, so you might be able to set up what are called packages in the product. That essentially restricts who can build against what integrations in that workspace, and you can put up different walls to say, you know, I might be the Okta owner, and I can build workflows against Okta, but I don't own anything that has to do with Workday, and so even though there's a Workday integration in the same workspace.

**Derek Zheng** [00:18:54]

I need to get, you know, approvals, or I have controls around building workflows against Workday, because that's not an app that I own.

**Derek Zheng** [00:19:03]

I'll quickly show where some of those configurations live in the product. So first, I can talk about ticket visibility. So here, I can define a visibility group. So, for example, you know, sensitive tickets.

**Derek Zheng** [00:19:16]

For Davison?

**Derek Zheng** [00:19:18]

This can be something that I match with a filter, so there might be, you know, a particular label, let's say, that

**Derek Zheng** [00:19:25]

I need to apply to a ticket that shows that this is actually a sensitive ticket and shouldn't be viewable by everyone else. You can kind of see all the configuration options here, pretty extensive in terms of the different ways you're able to cut and splice and kind of move tickets into these restricted visibility groups.

**Derek Zheng** [00:19:47]

On top of that… As I mentioned, a lot of the, kind of, restrictions or,

**Derek Zheng** [00:19:59]

Let's say, like, controls live at the individual, kind of, product area.

**Derek Zheng** [00:20:04]

So, for example, for databases, if you wanted to set up restrictions on, you know, who can see what, you might hit the permissions button here and say that, okay, look, like, I can see that this application service table is shared with several different

**Derek Zheng** [00:20:17]

team workspaces in my organization, and that's something that, you know, I can control as an owner of this database.

**Derek Zheng** [00:20:29]

Most importantly, I think, something that I see too, just to clarify, is the difference between a visibility group, which again is a permissions kind of sensitivity thing, assignment group, which is how tickets make its way to people, and then a view, which is how I cut and splice, kind of building a view of tickets that I can see.

**Derek Zheng** [00:20:49]

First one, ticket visibility group is obviously really important for sensitivities. You can see clearly how you can create walls of tickets, so only a certain group of people is authorized to see this ticket based on some type of rule. Assignment group is simply a group of users who, you know, has a schedule, who is in that workspace and can have tickets assigned to them. That assignment group might have a workflow or a assignment rule that directs tickets towards them, but that's

**Derek Zheng** [00:21:14]

Purely for assignment.

**Derek Zheng** [00:21:15]

And the last one is a view. So, you know, let's say I can view all the different tickets in the team workspace. You know, I might only

**Derek Zheng** [00:21:22]

even though I can see all the tickets, care about a particular area where I'm the subject matter expert. So, for example, maybe I'm just the hardware, you know, fulfiller, and that is the type of ticket that I care about. I can create views and save them to my personal scope to say, you know, based on a label or some type of category, if this request is hardware, then I can create a view that kind of customizes exactly what tickets show up to me.

**Derek Zheng** [00:21:45]

And I just want to make sure those concepts are clear to you all.

**Derek Zheng** [00:21:52]

Great. Well, I also think sharing is an important concept as well, so across databases, across workflows, across app connections, in the product today, you're able to, kind of as I showed.

**Derek Zheng** [00:22:05]

create

**Derek Zheng** [00:22:06]

these rules that share kind of content that lives in an individual workspace across to different workspaces. So, you know, in this case, I might be able to share my application service table with logistics, with internal audit, you know, maybe that's completely fine just based on how, you know, this table isn't sensitive, and so I can then kind of have other people consume to be able to read and write from these tables.

**Derek Zheng** [00:22:30]

Who might live in other workspaces.

**Derek Zheng** [00:22:33]

Additionally, when we talk about workflows, there's also the concept of sharing workflows, so the ability to say, hey, this specific workflow, I want IT infra, or the internal audit, or the security operations team workspace to be able to consume this workflow, which I still control, but another person can use it. That's something that you can also authorize the sharing. So, in that sense, I hope kind of what I mentioned earlier is clear.

**Derek Zheng** [00:22:57]

You can put up walls in between the workspace. You can also break down barriers between different workspaces and share and kind of

**Derek Zheng** [00:23:04]

Collaborate across those different boundaries.

**Derek Zheng** [00:23:10]

And just to, kind of.

**Derek Zheng** [00:23:13]

again, reiterate how all these different permissions and configurations make its way into, kind of, the lifecycle of a ticket. So, you might have a, you know, ticket from an end user come in via a, you know, DM experience, Slack, Teams, the email system. Serval will then, kind of, auto-classify

**Derek Zheng** [00:23:33]

you know, what team workspace does this belong to? And then within that workspace, you know, what is the category, what are all the different things that I need to automatically associate? Then, you know, Serval might

**Derek Zheng** [00:23:43]

use automations to try and resolve that. If that's not possible, it will escalate to an assignment group that you have configured, or find someone to pick up that task.

**Derek Zheng** [00:23:53]

And then it'll still be kind of inferring the status the entire time, and then kind of lead to that closure step. So, I think importantly, you can see how at the organization level, you know, I have defined who can actually create those tickets in the first place. And then in that inference step.

**Derek Zheng** [00:24:10]

what are the different workspaces that, you know, exist in my organization? Who can pick up work, how does that routing work? And then within those, like, who can see those tickets? How do those tickets make its way to people? All of those concepts in play, I think, are important to follow as that progression happens.

**Derek Zheng** [00:24:30]

I will also touch quickly on, like, visibility here, which I think matters for permissions. So, you may have seen when I created… I'll just jump to this workflow.

**Derek Zheng** [00:24:44]

Sorry.

**Derek Zheng** [00:24:47]

jump to this application service table again, the ability to kind of say to the help desk agent, what can you view out of this table? You know, we can scope this up and down to exactly what makes sense here, so whether this is

**Derek Zheng** [00:25:01]

You know, records that reference the requester, anything the requester can see based on their permissions or hidden, you can basically gate, for that end user requesting things, how much in your workspace is really consumable or visible to them.

**Derek Zheng** [00:25:13]

And I think most importantly, the concept of access profiles here is also really relevant, so you're able to then say, you know, in a similar way, you know.

**Derek Zheng** [00:25:23]

Who, based on their attributes, based on their group membership, based on a role in the product.

**Derek Zheng** [00:25:30]

is able to see or consume a particular automation. So that's another important governance aspect that isn't necessarily having to do with the settings and the product itself, but mostly to how you control what your end users can see.

**Davison Chung** [00:25:46]

Question from the group here around approvals. And so, is there a… is there a way to have a second layer of approval for any of the changes that are made by an admin specifically?

**Derek Zheng** [00:25:56]

Yeah, that's something I'll cover in just a second, but the short answer is yes. You're able to ensure that for all the different changes that you want to make to, you know, different

**Derek Zheng** [00:26:08]

workflows and resources in the workspace, that it always escalates or always gets confirmed by someone else in your peer group that isn't you. And then sometimes, you know, it makes sense to have people who are authorized to have that auto-approval happen. That's also something that you can set up, but short answer is that's all configurable.

**Derek Zheng** [00:26:31]

Awesome.

**Derek Zheng** [00:26:32]

So, importantly, I think for this recap of this section, I wanted to call out the two different levels of authority, so that first admin level, and that second workspace-level permissions, the ability to scope both of those to exactly what you care about.

**Derek Zheng** [00:26:46]

And then, I think on the controls within those workspaces, right, so custom roles, out-of-the-box built-in roles, and then also things like visibility groups, access controls, access profiles, all those are important to know. And then sharing between workspaces the ability to then kind of have other people consume and reuse what you've defined.

**Derek Zheng** [00:27:10]

All right, so now I'll talk about how these changes get approved, and kind of… I think it's a great segue with that question.

**Derek Zheng** [00:27:17]

First, an important concept is a, you know, there's a lot of drafted changes

**Derek Zheng** [00:27:23]

that could be possible in Serval. If you've ever built in Catalyst, you'll see that it proposes drafts of workflows, of skills, of dashboards, of, you know, configuration changes in the product, and that's something that you can kind of lock down in terms of who's building and configuring what. So, when I build something in the product here.

**Derek Zheng** [00:27:43]

you know, in Catalyst,

**Derek Zheng** [00:27:48]

I might see that, you know, this dashboard that I just built is actually sitting in draft. And that's something that I could directly publish, but I can also set that, you know, this

**Derek Zheng** [00:27:59]

button should propose something for review, depending on my role. I think that's a really important concept, because

**Derek Zheng** [00:28:05]

You know, not everyone should be able to directly manipulate things in production, to be, you know, making changes to, kind of, these critical workflows, and so that draft stage exists for a reason, to help cue and review those changes before something's actually published. When it's published, it's live, so to speak. It can be consumed based on the latest version that rolls out.

**Derek Zheng** [00:28:27]

And so, something that I see that I think is really powerful is, if you were to come to your settings here, into Catalyst, you can set up approval policies where you can say, okay, so if someone makes a change or drafts a change, are they able to directly publish, or is this something that has to be reviewed by a peer group? And this is, I think, a good

**Derek Zheng** [00:28:46]

kind of visual representation extension to that question earlier on the process of setting up approvals to get something to production. So first, you know, you might want to manually review the changes that you have as a builder and catalyst.

**Derek Zheng** [00:28:59]

does that draft look right? Does this look like exactly what I'm talking about? And then, you'll have to go through this approval flow. And that approval flow is something that you can configure here, so the ability to set different steps, to name specific users.

**Derek Zheng** [00:29:13]

to even use, like, a group, for example, or even a workflow to pull the latest of who should be able to approve something. That's all stuff that you can set up in these approval procedures here. And then again, if

**Derek Zheng** [00:29:25]

You know, I wanted to block people from self-approving, to that question. I can ensure that no one can self-approve, and instead it's something that, you know, I have to go to, you know, Doug to have him sign off before I make a change to any configuration.

**Derek Zheng** [00:29:43]

And so all of these different approval settings and, kind of procedures are, again, should look familiar, just because they're the same approval procedures used elsewhere in the product, but you can require this approval before publishing, which adds that specific gate here, before something is applied or published or made live.

**Derek Zheng** [00:30:04]

And I think, just to rehash what I quickly talked about in the product, so you can name specific approvers, you can configure a self-approval, you can add multiple steps where, you know, different groups are tagged at different points in a sequential manner, and that is all super important, I think, to identify from internally, you know, as a user of Serval, what is the right policy that corresponds to, you know, what the company deems is relevant.

**Derek Zheng** [00:30:30]

Now,

**Derek Zheng** [00:30:33]

the configurations that I've been showing mainly kind of cover the approvals and controls that you have developing within one environment, one workspace. And so here, you can see that, you know, if I was to set up

**Derek Zheng** [00:30:48]

this process of requiring approvals for Catalyst within this team workspace. You know, when I come to Catalyst and propose a new change.

**Derek Zheng** [00:31:09]

that, you know, this build process, the draft process, would actually use that policy. Now, sometimes it makes sense to have separate environments, as you see here. I have an IT team dev, and then actually an IT team production.

**Derek Zheng** [00:31:22]

Where these are separate environments with different applications, where I can develop more safely in the development environment, make my type changes, make my…

**Derek Zheng** [00:31:30]

kind of…

**Derek Zheng** [00:31:31]

complete my testing, and then, kind of promote this to a production environment. And the way that we do that today is via what we call team links. So Team Links here, allow you to create a

**Derek Zheng** [00:31:44]

kind of connection between one team workspace and another. And so, I might be able to link, for example, a new team. And what this allows me to do is kind of

**Derek Zheng** [00:31:56]

builds this pathway to promote changes up to a higher environment. And so here you can see that I have that IT team production promotion promotion set up. I can actually hit promote.

**Derek Zheng** [00:32:07]

And then what will happen here is, kind of, if you think about the approval process of

**Derek Zheng** [00:32:13]

you know, proposing something for review in the same works… same workspace, you're able to then promote things across workspaces to a higher environment. And so then you can select, you know, hey, these different access profiles, or this access policy, I want to propose this for review in the IT team production.

**Derek Zheng** [00:32:31]

Workspace, and that is all because you created that team link, and you set up that connection.

**Derek Zheng** [00:32:36]

So, here you'll see that, actually, Serval created an automatic summary of the different, things that, you know, I proposed for review here. Obviously, there's some errors that have shown up here that Serval's proactively finding for me, and so, you know, I might propose this, or I might not.

**Derek Zheng** [00:32:52]

And again, I think the most important thing with understanding these links is that they can still have the same gates where you name people, name a sequential number of steps, name groups to approve or sign off on a change being made and rolled out to a higher environment.

**Derek Zheng** [00:33:13]

Okay, other things that I quickly want to call out as I,

**Derek Zheng** [00:33:20]

and kind of on that section, before I move into recommendations is, again, the, you know, similar to how

**Derek Zheng** [00:33:28]

you could set up, cat list reviews, you could also set up reviews for who can actually sign off on an incoming promotion, for example. So, if you're in a higher environment in IT production, you can require, you know, approval, a review.

**Derek Zheng** [00:33:47]

Of folks who, need to,

**Derek Zheng** [00:33:52]

sometimes I think it makes sense to, when there's a change proposed in a lower environment, to still look at that change before it makes its way into the production environment from the production environment, and this is the type of setting that you're also able to configure, where if something's promoted or something's pulled.

**Derek Zheng** [00:34:09]

setting up those commencement policies to what you think is relevant. And again, you can review all these different promotions as they come in to publish them if they're approved. In this case, you know, my proposal here was auto-approved, or if,

**Derek Zheng** [00:34:27]

some changes being made by someone else to actually conduct the approval, to hit approve or deny and give a reason. This is the type of, kind of, interface that you're able to use as an admin as well, too.

**Derek Zheng** [00:34:40]

Guide all of these changes as they roll out.

**Derek Zheng** [00:34:45]

Awesome. So, I'll quickly walk through some final recommendations and best practices. So, first, I think understanding organization and team boundaries is important as we roll out Serval to new customers.

**Derek Zheng** [00:35:00]

By default, we usually start at having one organization with multiple different workspaces. You might have higher and lower environments for workspaces, or maybe not, right? So, sometimes people don't have the kind of complexity of a development environment, of a production environment, a validation environment.

**Derek Zheng** [00:35:17]

or don't want to have that process slow down their development speed. In those cases, you don't need to set up multiple organizations, you don't need to create all these different tenants, as it's a heavier weight process, and so you might just be able to operate out that one organization and set up those team boundaries as a starting point.

**Derek Zheng** [00:35:35]

In terms of how to scope these different workspaces, so, again,

**Derek Zheng** [00:35:40]

you need to identify, you know, what are the different departments or the different users across different areas of my company who might be able to benefit from, you know, the, power of Serval?

**Derek Zheng** [00:35:53]

We usually start at the, you know, asking the questions of, what are the departments who want to use Serval? Again, is that IT, HR, Finance?

**Derek Zheng** [00:36:00]

And let's start with each one of those different departments has their own workspace. Within that workspace, they're still able to govern across roles, across, you know, visibility restrictions, across other things, putting up walls and security within that workspace. And then depending on the organization, if your, you know, org looks very different than that model, then we can revisit how we draw those workspace boundaries. Is it one really large workspace? Is it several smaller

**Derek Zheng** [00:36:25]

workspaces, what makes sense. So these are the type of questions that I would start to ask about.

**Derek Zheng** [00:36:29]

Ask yourself, as you're, as you're kind of thinking through how to set up your organization.

**Derek Zheng** [00:36:35]

Other best practices, of course, are to start with the most restrictive roles, so the lowest level of agent, of read-only agent, and then try and progressively kind of escalate or create custom roles on top of that, depending on what you're seeing in production. Again, there should be very few org admins, there should be very few

**Derek Zheng** [00:36:53]

team workspace managers, that's all really important to… to get control over. And then.

**Derek Zheng** [00:36:59]

kind of the persona of what I see across the different workspaces for accounts is

**Derek Zheng** [00:37:05]

Of course, like, your platform owner will be an org admin, your workspace owner will be the manager of that workspace.

**Derek Zheng** [00:37:12]

And then you might have different people who are automation engineers, or process owners, who are, you know, just agents who work on tickets, maybe even requesters. Like, depending on that, you might give them certain roles in the team workspace, or even just no team role, and just an org member permission. So again, mapping and ensuring that you have the right, kind of.

**Derek Zheng** [00:37:32]

understanding of who should be where, that's kind of how we think about that. And then…

**Derek Zheng** [00:37:37]

as I mentioned earlier, like, that production-release cycle. So, for that workspace that you defined, take HR, take legal, is this a production-only environment where you have controls around role-based access controls and still approvals to ensure that those promotions are reviewed and vetted before they go live?

**Derek Zheng** [00:37:54]

Or do you have separate environments that you start to build out and set up so that things can kind of exist in lower environments to be promoted up? You know, what makes sense for you? That's really the question we see.

**Derek Zheng** [00:38:07]

And then most importantly, too, like, as you can see here, if I have 3 different workspaces in an organization, so IT, HR, and finance, I can see how, you know, HR and finance can actually skip UAT if that's not something that they really need. You don't necessarily have to have the same process for every single department. You know, if IT has a more rigorous process for, you know, governing some of the sensitive tools that they have.

**Derek Zheng** [00:38:30]

they can have a dev UAT, and production setup that is more robust than maybe something in HR or finance. Again, it just depends on

**Derek Zheng** [00:38:38]

what's best for your organization, and I think most importantly, we like to advocate for simplicity, so start with just a production workspace, or just a dev and production, and then validate if it makes sense to stand up a UAT environment. Again, because, you know, it becomes heavier weight, it becomes more of a process, overhead to set up, and so we obviously want people to build very quickly.

**Derek Zheng** [00:39:03]

Continuing to, move as fast as the ideas come to them, and so any additional step here creates additional friction that sometimes isn't as helpful, for folks.

**Derek Zheng** [00:39:15]

Cool. And then, yeah, other things I see are, you know, you might start with one workspace that… and that team figures out their best practices, what makes sense for them, so this might be IT who

**Derek Zheng** [00:39:28]

is the initial person who sets up the workspace and development model. They will become really familiar with how to scope and provision and kind of be the guinea pig of understanding what works for them.

**Derek Zheng** [00:39:38]

as that happens, that information can kind of be shared to the rest of the organization, right? To the other workspaces that are going to onboard to Serval. They can usually also be advocates or kind of share their knowledge about how that product works, which is really, really awesome to see.

**Derek Zheng** [00:39:55]

And then, yeah, finally, I think this is kind of more of a worksheet, so to speak, where, again, the exercise when you're thinking about how to tackle the Serval setup.

**Derek Zheng** [00:40:07]

What are the workspaces that you want to start off with? Who are the owners? What role should they be in? You know, what access restrictions do I need to have in place before I start having real tickets come in?

**Derek Zheng** [00:40:18]

You know, and then finally, what is, like, my release path? Do I have prod only? Do I have dev and prod? Do I have dev UAT, and prod? What makes sense, again, on my… on my specific…

**Derek Zheng** [00:40:28]

scenario. I think what's most important is to show that, you know, Serval has that flexibility, depending on what you want to do, around permissions, around controls, around approvals, you know, we can kind of meet you where you are in that way.

**Derek Zheng** [00:40:45]

Awesome! Well, I think that was a lot of content, and I moved pretty quickly, so let me know if there's any additional questions. Love the questions that we're getting so far.

**Davison Chung** [00:40:53]

Great, thanks, Derek. Yeah, I think a good question here from the group, which is, you know, a lot of companies will have a lot of this governance and approval flows, roles set up already in a different tool, and so if they're transitioning to Serval, what is the sort of pathway to going from what's already set up to replicated in Serval?

**Derek Zheng** [00:41:12]

Yeah, that's a good question.

**Derek Zheng** [00:41:15]

I think a lot of this will depend on that existing system, right? A few things come to mind. First is, you know, if you're able to integrate that system to Serval and have Serval read some of those permissions, or even export a matrix of permissions.

**Derek Zheng** [00:41:31]

You know, Serval can give good recommendations, Serval, as in the company, can give good recommendations about, you know, how to translate those concepts to workspaces, to different roles.

**Derek Zheng** [00:41:41]

And then as for setting up and configuring the product itself, it's generally pretty quick. A lot of this is stuff that

**Derek Zheng** [00:41:50]

kind of just has to be done, like setting up SSO and SCIM and making sure those foundations are laid correctly. That's usually what we see as, kind of the more fundamental and important things to get right before you get started, and so that exercise, of, I think.

**Derek Zheng** [00:42:03]

seeing what you have today, and depending on what system, and then kind of mapping that to Serval is… is how we start most of our deployments in general.

**Derek Zheng** [00:42:12]

The…

**Derek Zheng** [00:42:16]

Other thoughts I have are about, you know, depending on the specific application, again, if you already have groups defined for certain roles, we can ingest those and associate them automatically. There might be easy ways for us to, again, have Serval, the product, read some matrix of access and then automatically provision or add people to those roles. So, again, I think it would be case-by-case, but

**Derek Zheng** [00:42:36]

some… some efficiencies there.

**Davison Chung** [00:42:42]

Cool. Any additional follow-ups on that, Sonny, or anyone else?

**Davison Chung** [00:42:47]

Who's, contemplating the same.

**Davison Chung** [00:42:53]

Alrighty.

**Davison Chung** [00:42:55]

Well, I'll give folks some time to think of their last questions for Derek. It can be, you know, about what we've covered today, anything else that's come to mind while you all have been listening in. We have an extra 15 minutes, so we're happy to use that to answer questions folks have.


---

# Serval 202 - Journeys

Transcript from the Zoom Events recording, speaker and timestamp per turn.

**Davison Chung** [00:00:19]

UI redesign on, and so it's looking really good, and so excited to walk you through it.

**Davison Chung** [00:00:24]

In terms of where we're at, this is our 202 session on our Serval School curriculum, and so…

**Davison Chung** [00:00:33]

a little bit of a more advanced session, would highly recommend going and making sure that you've done the 101 series, the 102 series, so that you understand the sort of components that go into a journey. But…

**Davison Chung** [00:00:47]

Other than that, it should be a great session. As with all our sessions, please, let's make this interactive. Please use the Q&A, please use the chat. Feel free to raise your hand if you have a more complicated question or something that you want to go over live, and we'll take you off mute.

**Davison Chung** [00:00:59]

And we'll have more than enough time to go through whatever is top of mind for you all. So, with that, I'm going to hand it over to Owen to get us started.

**Owen Bishop** [00:01:09]

Awesome. Yeah.

**Owen Bishop** [00:01:11]

we will jump into it. So yeah, as Davison said, this is the 202, so please do ask lots of questions. I feel like the more, the better, honestly, for the session. And oftentimes, other people are thinking the exact same thing, but we can jump into it. So…

**Owen Bishop** [00:01:27]

super high-level topics for the day, really is kind of what is a journey, when to use them, what the kind of top use cases are. Of course, I think if you've used Serval, you'll see you can always use things for other cases, and people have wild use cases, but what the most common ones are.

**Owen Bishop** [00:01:42]

an example of kind of a journey build, and then also just Q&A, hopefully throughout it, not really only at the end. So, please chime in at any point with questions.

**Owen Bishop** [00:01:54]

But, jumping into it. So…

**Owen Bishop** [00:01:56]

A journey is, yeah, multi-step structure process, so very high level, you can think of it as just a step above workflows. So it's now building and actually combining multiple workflows into a longer structured process. So, think new hire onboarding, role changes, departures, stuff that has multiple steps that you really want to break out into different pieces.

**Owen Bishop** [00:02:20]

So instead of just one ticket holding everything, a Journey's gonna coordinate multiple tasks, multiple tickets across people, across even different teams in the org, and in the right order. So you can make sure that it's, you know, in a certain sequence, you can run things in parallel, and you can also have them be based on, you know, once we finish this, then this thing unlocks.

**Owen Bishop** [00:02:40]

So, everyone involved gets a view tailored to their role, too, which is pretty cool. So, for example, on a new hire onboarding, the new hire will have one view of the journey, the manager of the new hire will have a different view, so they just see, kind of, what their next few steps are gonna be. So, while a workflow is, yeah, that single thread of automated actions, it runs, it finishes, a journey is now a step out where that work is fanning out. So.

**Owen Bishop** [00:03:04]

It's across people, it's across teams, it's across time. It's adding just a couple more layers of complexity into organizing the different workflows.

**Owen Bishop** [00:03:15]

So, a couple key things to think of when you should reach out to our Journeys. So, multiple tasks being in a specific order, as I mentioned.

**Owen Bishop** [00:03:23]

If you have steps that have to happen in a sequence and not all at once, Journey is a perfect example for that where you can make sure it's sequential. So you do task a, then task b unlocks, you do task b, task c, so on and so on.

**Owen Bishop** [00:03:35]

You can have different inputs at different times, so equipment preference on, you know, day minus 5, emergency contact on day 1. You can collect them in stages, so it's not just one huge form. So, for example, in an onboarding.

**Owen Bishop** [00:03:47]

They maybe submit a bunch of stuff before their first day, and then on their first day, some new stuff unlocks that they then can actually fill out now that they officially work there. So, you don't have to, you know, have multiple forms for them, you can just have a single journey.

**Owen Bishop** [00:04:00]

The multiple stakeholders and teams, so splitting it across, you know, an employee, their manager, IT, HR. So, again, thinking of an onboarding, there's a lot of different people that get looped in for that. So you're gonna do, like, account provisioning, you're gonna be doing hardware order, you're gonna be doing, you know, a one-on-one with their manager. So, managing, you know, looping in all those different people.

**Owen Bishop** [00:04:21]

time-based steps, so some tasks, you know, shouldn't unlock until a date arrives, so first day instructions on the morning they start, for example, is a common one. We use it for, you know, onboarding here, so when I first joined Serval, I had my own journey, which on my very first day gave me a bunch of new tasks now that, you know, I worked here, whereas before that, I was already able to upload my name, sign some things, give a t-shirt size preference, stuff like that.

**Owen Bishop** [00:04:45]

And then dependent tasks. So, you know, no Google account until Okta exists, no welcome until accounts are provisioned, so you can make things blocked or gated on previous steps.

**Owen Bishop** [00:04:57]

also.

**Owen Bishop** [00:04:59]

The very high level, which I've already said a couple times, but the most common use cases for Journeys really being onboarding, so provisioning accounts, shipping equipment, all those different steps. Offboarding, so revoking access, basically the inverse, collecting devices, handoff responsibilities, all those different steps. And then job changes is a pretty common one, too. So, promotion, internal transfers.

**Owen Bishop** [00:05:20]

Any, yeah, essential partial onboarding, offboarding.

**Owen Bishop** [00:05:24]

And I call it here just being Journeys don't do the access provisioning directly, they'll just use the existing access provisioning stuff in Access Management, which is perfect, that's how it should be, because then you set things up there, and then a Journey can just call it, as opposed to having to redo or re-worry about any of those permissions.

**Owen Bishop** [00:05:44]

Awesome.

**Owen Bishop** [00:05:46]

So… I'll do this one, and I guess if any questions come in too, please do chime in, but…

**Owen Bishop** [00:05:52]

For a journey, you can think of it where every single step in that journey, every task, is a ticket. So it's just gonna be a parent ticket with a bunch of child tickets under it that are then in a specific order. And then each one of those tasks can carry workflows. So again, Journeys really just being a…

**Owen Bishop** [00:06:09]

way to kind of organize and utilize a lot of the different aspects of Serval, so workflows, tickets, all those different pieces.

**Owen Bishop** [00:06:17]

and have them in a very structured format. So, Serval Ticket under the hood, everything you already know about it applies. Due dates, SLAs, assignment groups, all those different pieces. And all of it can also be powered by workflows, so each task can carry a workflow with it. So.

**Owen Bishop** [00:06:33]

For example, you can think of a common one on this being… once they, you know, they have to submit their legal name for an onboarding. Once they submit their legal name, it then has a workflow that runs that uploads that over to Workday, or whatever HRIS you have. So, you can set up automations within each of these tasks, too.

**Owen Bishop** [00:06:53]

So any questions so far? Otherwise, yeah, keep chugging.

**Owen Bishop** [00:06:58]

Four types of tasks to call out. So a lot of this will probably sound familiar, but some cool stuff here. Manual, so this, like the one I just said, where someone is saying, you know, this is my t-shirt size or something. So an assignee does the thing, clicks mark complete. Example here, classic I-9 document verification.

**Owen Bishop** [00:07:15]

They can just click, yep, we did the I-9, so manual step being ticked off.

**Owen Bishop** [00:07:20]

A form, so an assignee filling out a form, and then it runs a workflow. So that's like the Workday one I just mentioned. So put in your legal name, click Submit, and suddenly the workflow runs and updates Workday. Make sure that you have, you know, their full legal name in there.

**Owen Bishop** [00:07:34]

Automated, being this is completely Serval-owned on this one, so the moment that something clears, we create a new task, and Serval actually owns this one.

**Owen Bishop** [00:07:44]

For an example, you can think of creating Okta, then Google wants Okta exists. So, you know, once they've done their I-9 or done their legal name or whatever, we run the Okta as its own ticket, but Serval will own it. It's not going to have to be picked up by a team member.

**Owen Bishop** [00:07:59]

And then last one being status checks, so pulling an external system on an interval. This is pretty cool, and I feel like oftentimes, yeah, background check being a good example here, so if you use, like, Checker.

**Owen Bishop** [00:08:09]

We can just pull it every hour or so for once their background check finishes, and then once it does, that task will autocomplete, too. So a way to, you know, link in some outside systems and make sure that they've done things in there, and that they're complete.

**Owen Bishop** [00:08:27]

And… Right? So…

**Owen Bishop** [00:08:30]

I think I've probably mentioned this a few times already, but really, again, to hammer it home, Journeys are just interdependent and cross-functional. So, you can have gates on tasks, on dates, on both, so you can have a gate around, you know, only open this task after their actual start date.

**Owen Bishop** [00:08:47]

or a gate around, only open this task after they have been provisioned on Google, or something like that. So, you can… you can make sure that things run, you know, in the sequence you want.

**Owen Bishop** [00:08:57]

And then it crosses team boundaries natively. So, with Serval, if you have, you know, your HR team has an environment, your IT team has an environment, maybe the HR team is the one that actually owns the journey, but then they can send tasks over to that IT team natively into their ticket queue, and the IT team can work from it there. So, one team owns the journey, but individual tasks can belong to any single team. So, each team will see what they own. It's assigned

**Owen Bishop** [00:09:22]

natively in their queue. It'll look very, very familiar.

**Owen Bishop** [00:09:25]

And everyone on the IT team, of course, or the HR team's example, can see the entire journey, but they wouldn't be able to necessarily do the IT-specific tasks. So there's not going to be opportunity for overlap there. And yeah, each team controls its slice, and the journey just tracks the entire, kind of, team… inter-team project.

**Owen Bishop** [00:09:46]

Great.

**Owen Bishop** [00:09:48]

Then, the three ways a journey starts. So, Journeys often carry data between tasks. So, for example, an account ID. So, this can, you know, go from step to step, and I'll show you in just a little, after a few of these slides, we'll jump into Serval itself, what this might look like. But you can just use Serval databases to hold these states, so it ties in with that piece of the puzzle, too. But then, for starting a journey, you can, of course, do it via the UI.

**Owen Bishop** [00:10:12]

So you can do, I'll show you, there's a new journey button on the Journeys page. You can start it from a workflow on a ticket. So say someone raises a help desk ticket, it can then spawn a journey and the journey will link back to that originating ticket. So you could set up some sort of workflow where if a manager messages in a certain channel, it starts a journey, maybe they did a promotion or something, they can say, hey, we're promoting so-and-so, starts up the journey for that promotion.

**Owen Bishop** [00:10:35]

Or, I would say the most common one is just fully automatic, so an external event will start it. For example, a new hire record appearing in Workday, so we automatically will then trigger a journey for that onboarding off of seeing that there's a new hire.

**Owen Bishop** [00:10:52]

Right.

**Owen Bishop** [00:10:53]

Then… continue. This will, of course, feel very common, but with Catalyst, as with most every part of Serval, you build Journeys with it, so… The real call-out here being just given the added layer of complexity that Journeys bring, the orchestration level of all these different workflows.

**Owen Bishop** [00:11:12]

being very specific with Catalyst is probably more important than sometimes with simple workflows and stuff, so making sure that, you know, you really are explicit about whether things are parallel, whether they're sequential, mentioning, you know, which reminders and SLAs need to be included, and

**Owen Bishop** [00:11:30]

Oftentimes, we see really great results for if you already have a flowchart, or if you have a CSV, or any sort of structured document outlining what your current

**Owen Bishop** [00:11:40]

You know, workflow, or…

**Owen Bishop** [00:11:41]

what you're currently using instead of a journey looks like, you can upload that to Catalyst, and it does a really good job of just replicating that same exact system and finding, you know, your one-to-one before you start iterating within Serval.

**Owen Bishop** [00:11:54]

And calls here again, you can do drafts for publishing, so same as with workflows there. It can just call in pre-existing workflows, which is pretty cool. So you can just, if you want, in Catalyst, at mention them, or you can usually just use their name, too.

**Owen Bishop** [00:12:07]

And the journey itself will just call a workflow that you already have built. And then publishing, yeah, exposes it to the help desk agent and to external triggers, so you can choose, you know, what actually creates… creates a journey, whether it's a message in a Slack, or, for example, the earlier one, like a Workday API call, anything like that.

**Owen Bishop** [00:12:29]

Awesome.

**Owen Bishop** [00:12:30]

I think, yeah, I was gonna say, I think that's it for the slides. So let me stop sharing briefly and I'll pull up Serval itself.

**Owen Bishop** [00:12:39]

While I do that, any questions just around the content from the slides, or around specific things?

**Owen Bishop** [00:12:45]

Anyone wants to see within Serval?

**Davison Chung** [00:12:49]

Yeah, and Owen's gonna show off, you know, again, those core use cases of onboarding, offboarding, you know, JML-type workflows, because that's when we see Journeys used most frequently.

**Davison Chung** [00:13:01]

But there are definitely other ways that you could use Journeys, use cases, and so we'd love to hear if people have other, other types of workflow, or other types of processes that they're looking to use Journeys for.

**Owen Bishop** [00:13:13]

Yeah.

**Owen Bishop** [00:13:14]

Awesome. Well… Within Serval itself, on the left, I can zoom in a little bit, too.

**Owen Bishop** [00:13:21]

Hopefully that's…

**Owen Bishop** [00:13:22]

nice and viewable for everyone. On the left, you'll see that there is a Journeys tab. If you don't have it on, I'm just in the demo team, but within settings capabilities, you can toggle it on, in the case that you haven't already. And this is the landing page for Journeys. So, here you can see all the different Journeys that are going on. This is our demo team, so there's a lot of incomplete ones, just because we're constantly spinning them up.

**Owen Bishop** [00:13:46]

But you can see a bunch of demo and employee newborn onboarding journeys over here. You can see completion rate at a pretty high level. And then this functions relatively similar to the tickets page. So you can create filters, you can create views, you can save them off.

**Owen Bishop** [00:14:01]

For your team. So, if you have a lot of different types of Journeys or anything like that, you can easily, you know, structure out this page as needed. But, I've already popped one open. I can just click it from here, too, though, I think. I think I popped open this one.

**Owen Bishop** [00:14:17]

Jumping into a journey itself?

**Owen Bishop** [00:14:19]

We do have some new fun UI pieces to this, which I think are, are exciting, but you can see basically each set of tasks.

**Owen Bishop** [00:14:28]

just going down from the owner for those tasks. So in this employee onboarding, for example, we can see Benji is our example for who is being onboarded, so you can see they have a couple tasks. They're grouped out into different categories, too.

**Owen Bishop** [00:14:43]

You can then see this, for example, is their manager, would have a couple of tasks, and then lastly, the team that owns this, so if this was the IT team, or someone may have a couple tasks, too.

**Owen Bishop** [00:14:54]

If I click here, this is what Benji would actually see. So if they're a new hire.

**Owen Bishop** [00:15:00]

this is what they would see. They'd see, oh, I can hop in, I have some tasks to do, here are the tasks. You can also see them in this very pretty UI. But clicking into any of them pops open those tasks, so you can see this is one of the manual ones, where you could then select your laptop model.

**Owen Bishop** [00:15:16]

I don't need a monitor and then choose where to ship it to. Let's just say the office and I'll click submit on that.

**Owen Bishop** [00:15:23]

Perfect. So, if I'm Benji, I'm now going, awesome, that's one task down, and you can see it's now running a workflow based off of that, too. Which is why it's spinning, and boom, it's checked off. So, for a new hire, it's an easy way to just go through the different steps you have.

**Owen Bishop** [00:15:39]

For the manager, same exact thing. You can see the steps you have, and then again, all of these loop up into just these different pieces.

**Owen Bishop** [00:15:46]

For this, too, you can see, for example, this step is locked at the moment. You can see that this task is gated, so it's gated on the manager actually… what is it? Approving the equipment selection.

**Owen Bishop** [00:15:59]

So once the manager approves the equipment selection, this task would unlock, so this is what we were speaking to earlier about you can either have things run in parallel or sequentially.

**Owen Bishop** [00:16:07]

So you can see a couple of these are definitely in parallel, where they're all open at the same time, but some of them also sequentially.

**Owen Bishop** [00:16:14]

And a new view we have for this, actually, is if you click Journey Graph, you'll be able to see all these different steps.

**Owen Bishop** [00:16:21]

And then what they unlock. So you can see this one unlocked by these. You can see, basically, this ship equipment to new hire is gated off of first, you know, approving the equipment selection. So it's a good visual for what things have been… have been unlocked.

**Davison Chung** [00:16:37]

Yeah. And there's a good question here, which is could Benji in this case view this before being onboarded?

**Davison Chung** [00:16:45]

And so before they are, you know, maybe have an official

**Davison Chung** [00:16:49]

I guess in this case, serve or email.

**Owen Bishop** [00:16:51]

Yeah, yep, in that case, we actually do that at Serval, so before I joined Serval, you can have it go out to, like, if he has a personal Gmail at first, and then Benji would just see those tasks from his personal Gmail and be able to get them going. For example, maybe…

**Owen Bishop** [00:17:08]

we can just say the NDA and the emergency contact, maybe those only spawn when he actually, like, after day one, though, so you could gate those on that timeframe.

**Owen Bishop** [00:17:16]

And then also, just using, if you have Okta or SSO or anything, when he joins and gets provisioned his actual email, you could then have the ownership of this move over to his actual email. So to his new company one. But yeah, you can absolutely have it

**Owen Bishop** [00:17:29]

pre-onboarding, and then also… or, like, pre-join, as well as post-join. That's what we do internally here.

**Davison Chung** [00:17:37]

Yeah, so would that show up… let's walk through that more. Would that show up as two different users, basically, here, with different tasks? A Benji personal, that is the pre-onboarding task, and then a Benji, you know, per, you know, work email that is post-onboarding tasks?

**Owen Bishop** [00:17:53]

You could do that. You could also

**Owen Bishop** [00:17:55]

If I go back to this journey overview, so if I see Benji here, you can see the example email. So you could absolutely have it broken out by those two. You could also have tasks on this Benji account. For example, we can use the NDA and the emergency contact that just are gated until he actually joins or until maybe his email is provisioned. And then as a part of the workflow of provisioning his email, you can then change the requester on this ticket.

**Owen Bishop** [00:18:20]

over to Benji's work email, in which case, this would just switch over to his different email.

**Owen Bishop** [00:18:26]

So you could absolutely do either two different Benjis, or you could just have it gated on Benji switching, once he gets a work email.

**Davison Chung** [00:18:35]

Nice, super cool.

**Owen Bishop** [00:18:37]

Yeah. Great. Then, yeah, the graph, I think it's super cool looking, especially with some really complex ones with a bunch of moving pieces. It's really helpful to see what gates what, and get an idea of, yeah, the interdependencies between these different workflows.

**Owen Bishop** [00:18:53]

But, I'll jump back to just the high-level view. A great call-out for… a lot of this, too, is just every single piece within a journey is tickets, so it all boils down to just Serval primitives that you likely already know. So if I click View Ticket, I'll just pop that open in a new tab.

**Owen Bishop** [00:19:13]

It will pull up this ticket, in which case you can see this is just essentially a normal ticket in the queue, but it was created by a journey, so you can then, of course, go back to the journey that it was created by. And at a very high level, you can see the parent ticket here.

**Owen Bishop** [00:19:30]

Which I'll pop open…

**Owen Bishop** [00:19:33]

Which then has all of the different subtasks. So, for example, on this journey, if I go back…

**Owen Bishop** [00:19:40]

We had new hire info, which has 3 subtasks. On this parent ticket itself, you'll see, of course, there is a new hire info subtask, which, if I click into, has those 3 subtasks. Actually, 4, because we've done one. So again, it all boils back to just

**Owen Bishop** [00:19:56]

tickets within Serval that just get nested as parents and then children, and then workflows that can be automatically triggered on those subtasks, and then the ability to navigate, you know, which tickets unlock which tickets. But yeah.

**Owen Bishop** [00:20:12]

Looks like we might have gotten a couple questions, too.

**Davison Chung** [00:20:16]

Yeah, I was just clarifying that the progress will, will save when you change the requester or owner of the future task. And so, if they've already confirmed the legal name and sent their equipment, all you're doing is changing who's responsible for the future tickets, you're not changing the status of past tickets.

**Owen Bishop** [00:20:35]

Yeah, no, that's a great call out.

**Owen Bishop** [00:20:36]

Oh, yeah. Awesome. Okay. Then, from there, yeah, we dug into what it looks like for those pieces. I think a great call-out, too, is… this one doesn't have it, but let's say, for example, we had a demo HR team.

**Owen Bishop** [00:20:51]

we could also have a section for them and send out a task to them, and then we're able to just monitor, hey, have they done that task yet? But then they'll receive that ticket natively into their ticket queue on that team. So it'll look like a normal ticket for them, it'll just show that it was spawned by a journey on, in this case, the demo team, but it feels very native for them, and then you're able to see visibility onto, hey, have they completed this task yet?

**Owen Bishop** [00:21:17]

Awesome.

**Owen Bishop** [00:21:19]

Other than that, I was gonna say one more thing before jumping to Catalyst, is I'd mentioned during…

**Owen Bishop** [00:21:26]

the demo, that oftentimes you want to, you know, save things throughout this. So, for example, maybe we need to save their…

**Owen Bishop** [00:21:34]

I don't know, user ID or something. In databases, there's a great place to do that. So just when you build out a journey, you can mention that to Catalyst, and in this case, you can see in databases, we have a table called Onboarding Records. New hire onboarding is written by the journey workflow.

**Owen Bishop** [00:21:50]

Which, if I click, you can see this then, each of these would have been one of our demo onboardings, but it's saving a ticket ID, the names, the emails, the managers, the start dates. So this is a great way to make sure that just information during the journey persists between steps. So if you want something from, you know, one of the first tasks to then be recycled into one of the later tasks, you can just natively use databases, which

**Owen Bishop** [00:22:15]

Catalyst can set up for you 100%.

**Owen Bishop** [00:22:18]

To make sure that that data persists across the entire journey.

**Owen Bishop** [00:22:26]

Then…

**Owen Bishop** [00:22:28]

the exciting part now is, yeah, how do you build some of these Journeys? So, on the Journeys page, from here, if you click New Journey.

**Owen Bishop** [00:22:38]

This is a list of all the Journeys that you have basically already set up in your team, so if you wanted, you could start another employee onboarding journey. I could click this to start another one for someone new. You can also see here, there's just installable Journeys. We have a sample employee onboarding journey, so if you want just a good starting point for one, you can just add this journey, and then work with Catalyst to, you know, modify it a little, and it gets you a good

**Owen Bishop** [00:23:01]

good starting point. But also, just in Catalyst itself, I think I had Tab open.

**Owen Bishop** [00:23:06]

If you click Browse Prompts, there's a couple under Journeys that just give you a good starting point again.

**Owen Bishop** [00:23:12]

for a couple different examples. So, onboarding, offboarding, role changes, and then provisioning laptops. So, all of these prompts are good, just demo starting points. They'll give you a, like, built-out journey that then you can iterate upon to actually fit more of your specific business practice, if you want.

**Owen Bishop** [00:23:30]

yeah, just a foot in the door already. Otherwise, of course, as mentioned during the slides, if you have any documentation around it already, that often is the best place, and honestly, more structure or more detail is better. I wouldn't worry too much about over-contextualizing your current processes.

**Davison Chung** [00:23:50]

Yeah. And I'll note that Catalyst can take in all sorts of different file types. Yeah.

**Owen Bishop** [00:23:55]

and.

**Davison Chung** [00:23:56]

file configuration so you don't have to, you know, whatever you have, you can try it, you can dump it in here and work with Catalyst to kind of configure it into the format it needs.

**Owen Bishop** [00:24:06]

Exactly. And then…

**Owen Bishop** [00:24:08]

On one of these Journeys itself, since we already have one, if I click on this just to pop it open.

**Owen Bishop** [00:24:16]

I'll close the run history. Here, you can see a journey, is essentially just a workflow. It'll even show up in your workflows list. So in this case, it's called Employee Onboarding Journey. If I went over to workflows, I'd be able to search for that. It just sits within there.

**Owen Bishop** [00:24:31]

But it'll feel very similar to stuff you've built before. It has the same UI of the high-level steps that are going to occur during this journey. And then, for a lot of these things, it's honestly just calling other workflows you have, or if you don't have them already, when it builds the journey, it'll also build the workflows it calls for those different steps.

**Owen Bishop** [00:24:50]

So, for example, if I click on a couple of these, I can just pull up on the left.

**Owen Bishop** [00:24:56]

Here, you're gonna see, actually, it has a bunch of child workflows, so all of these, if I actually, like, search through my workflows, we have a standalone workflow called Confirm Legal Name, and this journey is just orchestrating calling those in the correct order.

**Owen Bishop** [00:25:13]

So it's really just, yeah, an orchestrating tool for a bunch of different pieces of Serval that already exist.

**Owen Bishop** [00:25:21]

Awesome. I will pause there. Any questions so far? Otherwise…

**Owen Bishop** [00:25:27]

I think the next main step is really we can do a demo build-out of a journey, within Catalyst, but would love to just pause if there's any other pieces or questions that people have or want to see.

**Davison Chung** [00:25:40]

Yeah, any use cases for Journeys that are non-onboarding or off-boarding that people are interested in, or that we could, you know, chat through how you might set up?

**Davison Chung** [00:25:49]

Would love to hear those. Any other questions that have come up while we were going through this, feel free to let us know, but I think maybe if you want to start prompting Catalyst, and then while it's building, we can see if other people have questions.

**Owen Bishop** [00:26:05]

Since I always…

**Davison Chung** [00:26:06]

The way it's called, the way it's called, the email's called Zenergy.

**Owen Bishop** [00:26:12]

Let's do this one. Seems fun.

**Owen Bishop** [00:26:15]

We'll just start from the actual demo prompts.

**Owen Bishop** [00:26:25]

We'll join for this use case.

**Owen Bishop** [00:26:30]

And we'll start there.

**Davison Chung** [00:26:33]

And then while that's building, you know, I guess, have you seen other use cases for Journeys, or what are some other ideas that you see from customers that you've worked with that are not, I guess, the standard here?

**Owen Bishop** [00:26:44]

Yeah, good question. I think…

**Owen Bishop** [00:26:47]

Oftentimes it's almost extrapolations of the standard. The ones that I've seen, I've seen some really cool ones around like hardware requests.

**Owen Bishop** [00:26:55]

Which is pretty much this one, but you can even, like, wire it in. I've seen a customer wire it in to FedEx's API, so it actually, like, automatically creates a shipping label for them. They even actually print it automatically as part of the journey, which is pretty cool.

**Owen Bishop** [00:27:10]

So you can… anything that is multi-step, essentially create Journeys for it. The real call out there is.

**Owen Bishop** [00:27:19]

as long as it just needs some time gating or multiple people. Otherwise, obviously, like, a single workflow is the better approach.

**Owen Bishop** [00:27:28]

But yeah, I would say, I think…

**Owen Bishop** [00:27:30]

Great ones, hardware requests, is probably an underused one. Onboarding and offboarding are the obvious main ones.

**Davison Chung** [00:27:37]

Yeah.

**Davison Chung** [00:27:38]

Yeah, I think you can also think about it as, like, what are the playbooks that you have where there's a very set sequence of steps that different owners might own?

**Davison Chung** [00:27:46]

But happen sort of similarly in the same way every time. So, like, I've heard of examples of people who have, like, you know, they have a lot of, like, site management, and so they might have a journey that's, like, the IT site setup journey, right? So if you have a new location, you have a very specific set of things that need to be completed for a location, by various different owners in some sequence, and so tracking all of those tasks in a coordinated

**Davison Chung** [00:28:10]

Fashion is like one thing that you can do with a journey, for example.

**Owen Bishop** [00:28:16]

Have you heard of the Arabic accent?

**Owen Bishop** [00:28:20]

Still building, but while it does that, I think a couple things… oh, just finished. A couple things to call out, is again, Journeys really are just…

**Owen Bishop** [00:28:29]

A step up, basically, from workflows.

**Owen Bishop** [00:28:32]

but they're built under or alongside the same, like, primitives, essentially. So here you can see it has the same draft functionality, so you'll have the same publishing, and the same, like, reviews for Journeys as you do for workflows.

**Owen Bishop** [00:28:47]

So that'll feel similar. And then again, like, the entry point will feel the same as workflows, where you can customize, you know, right here, who it's coming from, and then this UI will feel very similar, too. But okay, perfect. We have…

**Owen Bishop** [00:29:03]

Draft up the journey with three step workflows. They're in the side panel.

**Owen Bishop** [00:29:07]

So, perfect, it's breaking it out.

**Owen Bishop** [00:29:10]

This first one will run automatically in check, automatically, and it opens for IT, once a laptop is reserved.

**Owen Bishop** [00:29:17]

And the thing here, again, to call out, is in building this journey, you can see it's actually building the workflows that it will be calling as part of this journey. So it will…

**Owen Bishop** [00:29:28]

Create, basically, all the little children workflows that we need, and then this journey itself is simply just calling them and looping them up into an organized building block.

**Owen Bishop** [00:29:38]

We're using them as building blocks, excuse me.

**Owen Bishop** [00:29:42]

But yeah, I'll say, unfortunately, I don't actually have publishing, because I'm in the demo team with the demo admin one.

**Owen Bishop** [00:29:47]

But… Yeah, maybe I'll jump over to the demo admin team, I guess. Any…

**Owen Bishop** [00:29:57]

Yeah, questions, really, so far?

**Davison Chung** [00:30:00]

I have a question based on something that I think comes up pretty frequently with journeys. Like, obviously these, you know, onboarding, offboarding as an example, but these journeys in general are often pretty.

**Owen Bishop** [00:30:09]

I.

**Davison Chung** [00:30:10]

they're pretty complicated. They have a lot of tasks, a lot of coordination, a lot of gating steps. What's your recommendation on how teams can collaborate to sort of make sure everything is working and, like, make sure the journey is working end-to-end, before deploying it in production, or, like, you know, monitoring it while it's in production?

**Owen Bishop** [00:30:27]

Yeah, that's a great question. In that case, so if I actually just jump back.

**Owen Bishop** [00:30:33]

To the journey itself, I'll pull it up.

**Owen Bishop** [00:30:37]

And that's the two that I filtered in this box.

**Owen Bishop** [00:30:42]

Let's see… so, yeah, on the Journeys itself, since everything really does just boil back down, into tickets, for anything that is, like, Serval automated, if you pop it up, you'll be able to click Run Details.

**Owen Bishop** [00:30:58]

Here you can just make sure that things are running successfully. So if there's any problems with a specific piece of the workflow, you'll be able to diagnose them here.

**Owen Bishop** [00:31:06]

And then, also, since everything is a ticket, if I just pop this open as a ticket itself, you can always open Catalyst on these and troubleshoot them if there ever are failures within the workflow, or things aren't running correctly.

**Owen Bishop** [00:31:20]

So…

**Owen Bishop** [00:31:21]

if a piece of it is broken, you can always jump into just that ticket, which has that specific workflow, and troubleshoot it with Catalyst.

**Owen Bishop** [00:31:28]

And the real just best practice, of course, I don't think this will ever change, is just as you publish one, just running it on, like, a demo account or your own account, just making sure that things do flow end-to-end, and then looping in any of those other teams that you are going to be sending those tickets to, just so people are aware that they are a piece of this journey.

**Owen Bishop** [00:31:49]

So obviously it is, like, a collaborative event, typically, where IT, HR, multiple teams are working on things, so making sure that just those different teams know that they will be

**Owen Bishop** [00:31:59]

Probably looped into these things as people submit them.

**Davison Chung** [00:32:04]

Do you know if simulations cover this?

**Owen Bishop** [00:32:06]

that.

**Owen Bishop** [00:32:07]

That's a great question. We can actually see all this.

**Owen Bishop** [00:32:13]

If I can pull up Edgerunning.

**Owen Bishop** [00:32:16]

Okay.

**Owen Bishop** [00:32:22]

It's okay.

**Owen Bishop** [00:32:25]

Yeah.

**Owen Bishop** [00:32:26]

Definitely do. So yeah, if you're using simulations.

**Owen Bishop** [00:32:31]

Cool. If you're using simulations, it's good for me, I'm learning. You can actually, yeah, loop in these Journeys as part of it. So if you're making use of, yeah, our native simulation ability, you can definitely use that. I think really with…

**Owen Bishop** [00:32:50]

Journeys, oftentimes, the…

**Owen Bishop** [00:32:53]

more difficult piece of it is just making sure that everything interweaves correctly, and it's less so the difficulty of the individual workflows. So it's…

**Owen Bishop** [00:33:03]

in general, expect simulations to be a bit of overkill, for the scenario. Simulations are typically more around, like, help desk agent.

**Owen Bishop** [00:33:13]

you know, context and calling. But yeah, you absolutely could, if you wanted to. I think the big thing really being…

**Owen Bishop** [00:33:21]

testing, and just making sure that it works for an account, and then whenever things do pop up, you're able to just pull them up, if I go back. With Catalyst, which is extremely helpful for just diagnosing any bugs as you hit them.

**Owen Bishop** [00:33:35]

Oh, wow.

**Owen Bishop** [00:33:37]

But yeah, and of course, yeah, all of these are tickets, so you can always pop any of them open with Catalyst.

**Owen Bishop** [00:33:46]

Well, potentially.

**Owen Bishop** [00:33:49]

Yeah.

**Davison Chung** [00:33:50]

Yeah, I think the question is more about like, yeah, how do you test end-to-end? Can you use simulations? How do we protect against regressions?

**Davison Chung** [00:33:57]

In this type of, in this type of scenario.

**Owen Bishop** [00:34:00]

Yeah, how do we, sorry, protect against…

**Davison Chung** [00:34:04]

regressions.

**Owen Bishop** [00:34:05]

model.

**Owen Bishop** [00:34:07]

Which I think…

**Davison Chung** [00:34:08]

be.

**Owen Bishop** [00:34:08]

And like it did work and now it doesn't.

**Davison Chung** [00:34:11]

That's right.

**Owen Bishop** [00:34:12]

Okay. Yeah. For that, I would say because it simply is a step up from workflow, and it's just calling workflows.

**Owen Bishop** [00:34:23]

For, like, these workflows, if I, like, pop one of them open, they would all follow the same publishing rules as anything else, so if you already have

**Owen Bishop** [00:34:32]

like, strong publishing rules, it'll follow those. You could also use multiple environments if you do that and, you know, promote a journey, or promote its, you know, children workflows.

**Owen Bishop** [00:34:44]

From a sandbox environment over to production. And then oftentimes I've seen, I think, good strategy is you can just set up a rule, as a catalyst skill.

**Owen Bishop** [00:34:53]

For any workflow that is part of a journey, you can just add a Journeys tag.

**Owen Bishop** [00:34:59]

So in this case, we didn't have one, but you could create a journey tag. And that's just an easy way for when reviewers are going through things to understand that this journey is part of a bigger picture.

**Owen Bishop** [00:35:09]

And to just review it with that knowledge. I think that's often helpful, since it just does look like a workflow, it is a workflow, but it has that additional context of being, you know, part of a journey.

**Owen Bishop** [00:35:23]

No.

**Davison Chung** [00:35:24]

Awesome.

**Davison Chung** [00:35:25]

Yeah, and just as a reminder, tags are what go on workflows to sort of categorize and move them around. Categories and labels are what go on tickets to do the same type of functionality. But all different systems for organizing.

**Owen Bishop** [00:35:40]

question.

**Davison Chung** [00:35:40]

the various primitives within Serval.

**Owen Bishop** [00:35:44]

Yeah, awesome. Any other questions from the chat? I guess I can probably work too.

**Owen Bishop** [00:35:49]

Got it.

**Davison Chung** [00:35:50]

No other questions right now, and so I think that this is most of the content that we wanted to show people, walking through the kind of concept of Journeys, how they're constructed, the different components of them, showing you some examples of how they're built and what they might look like for the different users who are using them, and then obviously collaborating with Catalyst to help you build and test them.

**Davison Chung** [00:36:09]

And so, you know, we have 20 minutes left. We're happy to stay on and answer more questions people have. There's certain scenarios or kind of tasks that people are concerned about integrating into their journeys, feel free to let us know and put it in the chat. I'll just give a quick

**Davison Chung** [00:36:24]

plug for what we have going on with Serval School and where we're at in that. I know they said this at the beginning, but this is the middle of our 202, sort of advanced series of webinars. The advanced series of webinars are meant to take everything you learned in Foundations and apply it to more complex concepts within Serval, in this case, combining

**Davison Chung** [00:36:44]

Ticket types, workflows, catalyst use, skills, all into these kind of more complex, longer-running journeys.

**Davison Chung** [00:36:52]

And so we, you know, obviously we're almost at the end of the week. We have one more session tomorrow, which is on governance.

**Davison Chung** [00:37:00]

teams and permissions. That's a great one for admins or team managers who are trying to figure out all the settings and configurations for their team to make sure that they have the right permissions and abilities within Serval.

**Davison Chung** [00:37:12]

And then next week we'll restart with with 101 through 103 if you missed those this week, as well as some of our other advanced topics, databases, and then ITIL and Serval.

**Davison Chung** [00:37:22]

Yeah, so all of that can be found at, Serval School, Serval.com slash Serval dash… sorry, Serval.com slash Serval dash School, which I'll put in the chat. And if you have any questions about anything Serval School related, you can always reach out to me, Davison at Serval.com, which is also in the chat.


---

# Serval 203 - Core ITIL Practices in Serval

Transcript from the Zoom Events recording, speaker and timestamp per turn.

**Davison Chung** [00:00:00]

All right, hello everyone. Happy Friday. Hope everyone is looking forward to the weekend. Excited to welcome you all to our inaugural Core ITIL Practices in Serval webinar. I'm joined by George, he's one of the founding members of our deployment team, and so George is going to walk you through all the content. I'm really excited for this one. This is one that people have definitely been asking for.

**Davison Chung** [00:00:23]

And so, please feel free to use the Q&A, use the chat, raise your hand if you have a complicated question, we can take you off mute. We want this to be interactive, we want to make sure that we're answering all of your questions, and this is a session that's useful for you all. And so, with all that said, I'm going to pass it over to George.

**George Fang** [00:00:43]

Alright, thank you guys all for being here.

**George Fang** [00:00:46]

Well, quick check, can you see my screen? I'm presenting slides on. Okay, cool.

**George Fang** [00:00:50]

Well, yeah, I'll introduce myself real quick. I'm George, I'm one of the deployed software engineers here at Serval. Been around for a good amount of time. I primarily work on the product, as well as with a wide variety of customers and their deployments with Serval. So yeah, I'm really excited to share core ITIL practices in Serval. This is going to be our Serval 203.

**George Fang** [00:01:08]

Where we cover, primarily.

**George Fang** [00:01:11]

the core ITIL Practice Management's practices within Serval, which are requests, incidences, and major incidences, problems, and changes. We'll also touch on two additional ticket types, which are our custom ticket types, and then our task ticket types.

**George Fang** [00:01:28]

From a high level, just want to share this slide to frame how we approach ticket types in Serval, and then I'll show you what that looks like in practice from three main personas. One, which is going to be the end user, so end users submitting requests or reporting instances.

**George Fang** [00:01:43]

Two, it's gonna be agents, so how do you handle these types of tickets?

**George Fang** [00:01:48]

And what does that process look like navigating Serval on the back end with these ticket types? And then the third persona is going to be team workspace managers. So what does it look like to configure these ticket types within Serval, and how do you do that?

**George Fang** [00:02:01]

From a high level.

**George Fang** [00:02:03]

for each of these core practices, or ticket types, there's gonna be four main configurations. One, the statuses, or the allowed status states that that ticket can be in, as well as, the life cycle that each of those statuses… that that ticket can go through between statuses.

**George Fang** [00:02:23]

We'll have the status entry workflows, which is really, like, the automation engine and more of that automation piece that you can enable on different ticket types.

**George Fang** [00:02:31]

We have our…

**George Fang** [00:02:33]

state machine transitions, so transitions is something that's fully configurable if you want it to be. And then we can also set up conditions that require tickets to have certain properties before being able to move from one status to another.

**George Fang** [00:02:45]

And then conditions and custom fields really work together to help, build out what are those… the framework behind the status transitions.

**George Fang** [00:02:55]

I think to make this a lot more real and easy to follow, I'm just gonna jump right into Serval itself, and

**George Fang** [00:03:05]

Fire off.

**George Fang** [00:03:07]

a few, or I guess I'll start, actually, in the tickets types page, and show you guys what this looks like from that third persona, which is going to be that team workspace manager.

**George Fang** [00:03:17]

So…

**George Fang** [00:03:19]

Ticket types are gonna be within the team workspace settings, so once you're in a team workspace, you'll navigate to Settings, and then within the team workspace settings, you'll go to the Ticketing section, and you'll find ticket types.

**George Fang** [00:03:30]

Here's where you can manage all the different ticket types, that the team workspace enables. I think by default, we'll have requests on, but you can also turn on optional types of incidences, major incidents, change, problems, these journey ticket types, and then your own custom ticket types.

**George Fang** [00:03:48]

Once you're in the ticket type page, you'll configure the model of the ticket within the ticket type itself. So I'll go and start in requests.

**George Fang** [00:03:58]

So this is sort of the classic view, is where you'll have… you'll define the statuses that a ticket type can be in.

**George Fang** [00:04:06]

Here we have, you know, 16 different status… potential status types for request.

**George Fang** [00:04:12]

And we've toggled on set status with AI. And so this means Serval is going to be able to move tickets between all these different statuses that have toggled on selectable by AI. So what this means is, in practice, a request can move between to-do, in progress, triage, investigating, etc, all these different ticket types. And Serval's gonna do and handle that movement for you based off of the description of the status.

**George Fang** [00:04:40]

So, another thing that's kind of important to note is that,

**George Fang** [00:04:44]

With this transitions toggle off, Serval is setting the statuses with AI, and their quest can move freely between any of the statuses defined above. These still define and set what the status is or the collection of statuses are, but for requests, often this is a free-flowing and free-moving platform, and so we won't have transitions on.

**George Fang** [00:05:03]

I'll dive into what transitions are and what they enable in further ticket types.

**George Fang** [00:05:08]

But really want to just focus on requests here, where we have the set of statuses a request can be in.

**George Fang** [00:05:13]

And then the custom fields that we're going to collect. And so here, there's two things to note, or there's two layers. One is the status section, so we have five sections of… or sorry, not the status section, the custom field sections.

**George Fang** [00:05:25]

So we have 5 sections of custom fields that we could collect, based off of the type of request that this is, right? So if this is an HR request, we've got, you know, we would want to define the fields that we're collecting there. If this is procurement-related, we have a set of procurement-related fields that we want to collect there.

**George Fang** [00:05:42]

So I think…

**Davison Chung** [00:05:42]

Can you have a status for each form?

**George Fang** [00:05:47]

What do you mean by form?

**George Fang** [00:05:49]

Like, for each… for a status for each ticket type, or form-based statuses?

**Davison Chung** [00:05:55]

Katrina, I'll let you, specify a little bit more for each catalog, I guess.

**George Fang** [00:06:04]

Each ticket type will have its own set of statuses, so if there are multiple catalog items or forms that kick off the same request, that's gonna fall through the same, statuses per ticket type.

**George Fang** [00:06:15]

But what you could do is here, you know, if you want this to be different per ticket type, we can set up different automations that, based off of the catalog request, it kicks off a ticket and loads it into a certain status, rather than this other form, maybe it's a different procurement request, would create a request-type ticket, but then kick you off into a certain status

**George Fang** [00:06:34]

To differentiate that.

**George Fang** [00:06:36]

Let me know if that helps answer that question, or if you have any follow-ups there.

**George Fang** [00:06:40]

I think what might be helpful, then, is to see this from the end user perspective. So, if you guys can all still see my screen, I've just moved over to a different window, where I'm now taking on the persona of an end user, where I have… I don't have any access to these different team workspaces, and I'll submit a… a simple request, such as, you know.

**George Fang** [00:07:00]

I need a new computer.

**George Fang** [00:07:10]

Another thing to note is there's two types of tickets that end users are able to create naturally.

**George Fang** [00:07:16]

The other ticket types are something that is going to be handled by agents or team managers of the workspace itself.

**George Fang** [00:07:21]

And the two that end users are able to create are requests and incidences. And the way that Serval determines what type of ticket the user's message is going to become is based off their description here.

**George Fang** [00:07:32]

A request you should think about is anything that's net new, something that's, hey, I need new access, new equipment, I'm looking for information that could be new information or a specific service, versus an incident is something that's broken or not working as expected.

**George Fang** [00:07:46]

So, in the request that I fired off, I need a new computer. This is something that's net new, this is gonna be of type request.

**George Fang** [00:07:54]

And what we have configured here is a form, and so I can go and choose my laptop model. This isn't necessarily, you know, critical for this demo, or this explanation of ticket types, but for the sake of this, I'll fill this out so you can see and kind of simulate what this ticket type is going to look like.

**George Fang** [00:08:17]

Great.

**George Fang** [00:08:19]

So I'm gonna submit this ticket as the end user.

**George Fang** [00:08:21]

as a… now, switching over to the agent's perspective, or the agent's persona, I can go look at my tickets and see that this new ticket type request just came in.

**George Fang** [00:08:32]

And what's really nice is I see all the action happening on the ticket, but then on the right side, where we had configured custom fields on that ticket.

**George Fang** [00:08:41]

I'll pull up that tab again.

**George Fang** [00:08:45]

We've also done something here where we've said, hey, AI, you can select what, or you can help me set these fields based off of the context of the ticket.

**George Fang** [00:08:53]

So under this procurement section, we have these 12 different fields, and we've defined the name of the field, and then the type of data that we're trying to collect.

**George Fang** [00:09:02]

This can be… Let's find an example here.

**George Fang** [00:09:09]

So this can be of type text, number, boolean, a date, an enum, which would be a multiple choice value, an item reference, which pulls directly from our CMDB or database, it can be a user reference, a multi-select, or even a file here.

**George Fang** [00:09:23]

And so what we've done is Serval's actually gone through and filled out some of this information for me. It realized, hey, I need A new computer, it's gonna be of quantity 1, this is hardware-related, specifically the procurement item they're looking for is computer,

**George Fang** [00:09:38]

And then, as the agent, I can go in and fill up these additional fields. Okay, great. Maybe if there was something in our database that told us what, you know, how much this model of computer costs, that would be something that would be filled in automatically. Otherwise, I can go in and say, yeah, this is a $1500 computer, save that there for, you know, future reference.

**George Fang** [00:09:57]

So I can go ahead, too, as the agent.

**George Fang** [00:10:01]

look at this ticket, look at this form, I can approve this.

**George Fang** [00:10:05]

And fire off the rest of this request.

**George Fang** [00:10:08]

Cool. So, that's requests, requests.

**Davison Chung** [00:10:12]

about requests, George.

**George Fang** [00:10:13]

Yeah.

**Davison Chung** [00:10:14]

So one is, can you set it up so that a request will wait for an approval before it actually gets submitted and fulfilled?

**Davison Chung** [00:10:23]

Interesting.

**George Fang** [00:10:24]

What happened… yeah, go ahead.

**George Fang** [00:10:26]

No, I think… I think that approval process, what you're looking for would want to be owned directly on the form or the catalog item that the user's submitting. So, by default, we want to track every ticket.

**George Fang** [00:10:37]

or every conversation with Serval as a ticket, whether that's going to be looking for knowledge articles, submitting an actual request for our hardware. The piece, the gating piece that you're going to want to set up

**George Fang** [00:10:48]

isn't allowing them to even create this ticket, it'll be the flow of the form itself. So I think what you just saw here is a great example where the end user is submitting a new laptop request. As an agent, I'm on this platform, I see that this ticket has already come in, I'm on the help desk, and I can go approve this laptop request.

**George Fang** [00:11:07]

Does that help answer that question?

**Davison Chung** [00:11:10]

Yeah, I think so. I think the question was basically, like, could you set it up so that the request isn't even logged until they know it's gonna be approved?

**George Fang** [00:11:19]

Got it, yeah. The request will be logged right away, so that… I think it's really important to have that system of record, and see that that ticket comes through, and then the approval will live on the ticket itself, so that you keep track of, hey, if that is denied, we want to have track of that, that that ticket was created, a request was made by a certain user, and it was denied for this reason.

**Davison Chung** [00:11:37]

Yeah, definitely. And then for requests, is there a way to build, like, a standard catalog template that other teams can use? So, like, a master template?

**George Fang** [00:11:49]

Okay, yes, so I think what that would be is, like, your master template for your team workspace would live in,

**George Fang** [00:11:57]

ticket types here, and so you'd want to build out… I think the question is, you want to build out a template that all other team workspaces can use.

**George Fang** [00:12:03]

As it exists right now, ticket types are owned by your team workspace. So the IT team, or HR team, or legal, or procurement team, each owns their own set of ticket types. As we start to develop and

**George Fang** [00:12:18]

build upon our promotions, or SDLC product, which I'm sure we'll cover in a later, Serval 200 level class, you'll see that these ticket types can be promoted between teamwork spaces, and so if you do have one kind of overarching,

**George Fang** [00:12:33]

I'd say, like, organizational-level team workspace that you want to own the ticket type

**George Fang** [00:12:41]

templates, then that could be something that's shared between teamwork spaces, but as it exists right now, ticket types are going to be owned by the team workspace on a team workspace level.

**George Fang** [00:12:49]

Shit.

**George Fang** [00:12:51]

Cool. Cool.

**Davison Chung** [00:12:53]

Good questions. All good questions, please keep them coming.

**George Fang** [00:12:57]

Okay, cool. So now, let's move on from requests to incidents.

**George Fang** [00:13:00]

I'll go back to the end user persona, and I'll submit a couple different tickets, something like, hey, my computer…

**George Fang** [00:13:07]

Isn't connecting.

**George Fang** [00:13:09]

to the VPN.

**George Fang** [00:13:13]

Or…

**George Fang** [00:13:17]

Something like… The lights in the… SF, Office…

**George Fang** [00:13:27]

Are off, and the light switches are not working.

**George Fang** [00:13:35]

So, as you can see here, tickets that are categorized, or kind of a message sent to Serval where something isn't working as expected, something is broken, those are going to be auto-categorized as incident tickets.

**George Fang** [00:13:48]

Computer isn't connecting to VPN, so Serval's gonna, you know, go ahead and build out… run out the automations that we've set up and configured for this team workspace, for incident-type tickets.

**George Fang** [00:13:59]

Same thing here for the SF office lights and switches are not working.

**George Fang** [00:14:03]

I think something that is interesting that I want to call out here is on this ticket itself, so switching back to the agent perspective.

**George Fang** [00:14:10]

maybe I see this… this message come in, and…

**George Fang** [00:14:13]

really what the user's asking is after a little bit of back-and-forth triage, they just want some technician to come in and turn the lights on, and so maybe I want to classify that as a request. What I can do here is I can reclassify this ticket as a request. So incidences and requests can be interchangeable, and even if the statuses that

**George Fang** [00:14:31]

a incident go through are different than the statuses that a request go through. What we'll do is we'll map the status group.

**George Fang** [00:14:38]

And so what I mean by that is.

**George Fang** [00:14:40]

Each ticket has 4 different status groups. We have to-do, In Progress, Done, and canceled.

**George Fang** [00:14:46]

Within each status group, there's your own customizable, specific statuses. So, those statuses and requests might be different and are different than the statuses that exist in Incident, but what we'll do is we'll map

**George Fang** [00:14:58]

If the current status for the request is in the in-progress group, when we reclassify that as an incident, it'll map over to a status in the in-progress group for incidences.

**George Fang** [00:15:11]

So, statuses, or sorry, requests and incidences both have enable transitions off,

**George Fang** [00:15:19]

So, I want to call out, or I wanted to just show you what that looks like from an end-user perspective, the ability to, you know, submit any message that you have, and have Serval auto-classify that as an incident or request, and then have Serval fill in the custom fields that you've configured.

**George Fang** [00:15:36]

Granted that you've toggled on, Serval's able to help you set those custom fields with AI. Here on this incident ticket, it's given me a summary, recommended action, and then it's even filled in my severity, my impact, and my urgency, all which kind of boil up to become this priority metric.

**George Fang** [00:15:55]

Cool. Any questions on incidents?

**Davison Chung** [00:16:02]

Both incidents and…

**Davison Chung** [00:16:04]

I think the question is basically, do incidents and service requests have the same, numbering system? And so.

**George Fang** [00:16:10]

Did you miss something.

**Davison Chung** [00:16:10]

Yeah.

**George Fang** [00:16:11]

Oh, yeah. Go ahead. Yep, so all your tickets will share the same numbering system as all these tickets come in, Serval will kind of, you know, incrementally… I think that's the question, right, Davison?

**Davison Chung** [00:16:22]

I think so. No, but you can, clarify if not. And then…

**Davison Chung** [00:16:31]

I'm not sure… Manisha, I'm not sure what your question is here. If the ticket module doesn't work, which is built with the help of AI option, how will this be fixed?

**George Fang** [00:16:44]

Vanish, are you referencing this?

**Davison Chung** [00:16:46]

Is the question, can you use Catalyst to help you build these ticket types, or, like, configure your ticket types?

**Davison Chung** [00:16:55]

maybe if you can clarify for me in the chat, or I can, take you off mute and you can ask your question either way.

**Davison Chung** [00:17:08]

I think… Sorry, go ahead.

**George Fang** [00:17:12]

Yeah, what I can maybe try to help cover here is two pieces, Manish. One, if your fields or your statuses aren't set with AI, that's also fine. That process would just happen manually, where you would go into a ticket, and you could move, you know, the ticket between statuses.

**George Fang** [00:17:30]

I think the other piece that maybe you're wondering is how can, you know, if those fields aren't set with AI, is there another way to leverage that? And what Davison called out here is also, we have catalyst that lives in the ticket itself, and so I can say, based on the ticket context.

**George Fang** [00:17:45]

Can you… Let me do this on the incident.

**George Fang** [00:17:52]

So I can say, hey, based on the ticket context, can you help me Fill out.

**George Fang** [00:17:59]

More of these.

**George Fang** [00:18:01]

custom fields.

**George Fang** [00:18:05]

So, even if AI is toggled off, you still will always have this catalyst, which is our backend agent helping you fill out or complete the details on these tickets. I can even have Catalyst help me create additional tickets off of this ticket. So, something I'll show later on is the ability to derive tickets based off of

**George Fang** [00:18:24]

pre-existing tickets. For example, I have this incident, I want to derive a problem. Or I've got a major incident, I want to derive a change. Catalyst can also help you do that.

**George Fang** [00:18:33]

Manish, let me know if that helped answer your question, or if you have any follow-ups here. I'm happy to dive deeper in that.

**Davison Chung** [00:18:39]

Few more questions, here. How does the… can you talk about how the priority works across the different ticket types, and whether it's auto-set, or if there's a manual option for the different record types?

**George Fang** [00:18:50]

Yeah, definitely.

**George Fang** [00:18:52]

So, priorities live also in team workspace settings underneath the ticketing section and priorities. Here we have 5 different priorities, which you can rename, you know, some people have a P0 through P4 scale.

**George Fang** [00:19:03]

But the most important part is turning on selectable by AI, and then giving that priority a really strong description. Priority is going to be a metric that's based off of, you know, impact times severity times,

**George Fang** [00:19:16]

urgency, but ultimately, what Serval's going to be doing, it's going to be re… Serval will read the context of the ticket.

**George Fang** [00:19:23]

read the descriptions that you've given each of these priorities and find the best matching for the priority to the ticket. I think what this helps solve is, oftentimes, you know, users would come into Serval if they could manually set their priority, they just want their request or their incident solved first, or solved fastest, and so they're always going to go manually select the highest priority.

**George Fang** [00:19:41]

In this case, Serval's going to do so intelligently, but as an agent, you still also have full control over going into a ticket and changing the priority manually yourself.

**Davison Chung** [00:19:53]

Cool. Going back to the ticket numbers, can you just show again, like, how the different tickets show up? I believe… so the question is basically, do they show up with different, like, front name tags? I believe that the front tags are all determined by the team that you're in, and then the number is just sequential, and so…

**Davison Chung** [00:20:10]

Incidents requests are tagged in the, in the title there, and in other,

**Davison Chung** [00:20:14]

you know, in the type of the ticket, but not in the ID number.

**George Fang** [00:20:19]

Yep, that's correct. So you'd set your prefix here in the team workspace settings.

**George Fang** [00:20:24]

And then, like Davison said, we'd count sequentially. I think what might be helpful is to break up these… this queue into different types of tickets. What you would do is maybe create a new view, and this is going to be my incidents.

**George Fang** [00:20:36]

And then I would add a filter here to say, I only want to look at ticket types that are of typed incident, I'm going to create this view. Now, I'm an agent, I've come to Serval, I'm opening up my laptop, the first thing I want to check is just make sure I'm going through all my instances and clearing those out.

**George Fang** [00:20:51]

And so, building out these ticket queues is gonna be the best way for you to have this quick view on different types of tickets.

**Davison Chung** [00:20:58]

Yeah. And then there's a question about, you know.

**Davison Chung** [00:21:01]

Since the ticketing is using the same numbering system, does it mean that in the back end, all of these are lying on the same tables?

**Davison Chung** [00:21:09]

It's a more technical question for you, George.

**George Fang** [00:21:12]

Yeah, we do have a single tickets table that will keep track of all these tickets, and obviously we differentiate by ticket type.

**George Fang** [00:21:20]

But…

**George Fang** [00:21:21]

as kind of shown out here, each of these tickets is really customizable, and so we can have different options exist on each of these different tickets, that I'll get to later on.

**George Fang** [00:21:32]

Holds?

**Davison Chung** [00:21:33]

I think that that is all the questions for now. Thank you, everyone. We'll let you get back to your… to what you were planning on showing next.

**George Fang** [00:21:42]

Yeah, sweet. So, I think now we want to jump into some of that more interesting stuff, where we're past that end-user perspective of requests and incidences. You know, one or two people submitting the same incident.

**George Fang** [00:21:54]

is sort of a cluster. We've got 200 of the same, that's gonna be a major incident. So, as the agent on the platform, what do we do, right?

**George Fang** [00:22:03]

Before I create a major incident, I want to talk through the major incident ticket type, which is one of the more unique ticket types, and talk through the different pieces of it. So, previously, what you've seen are the status section and the custom field section, but then there's also the transition section, and this is what really starts to make these ticket types more meaningful and more impactful.

**George Fang** [00:22:23]

So within transitions, once we enable transition, we're basically saying this ticket type needs to go through these specific statuses in this specific order, given these specific conditions.

**George Fang** [00:22:33]

So the first thing we're gonna do is identify the status lifecycle. And here we're saying it's gonna go through this approval, in progress, hold, review, done state, potentially also optionally canceled or rejected.

**George Fang** [00:22:45]

Then we're defining

**George Fang** [00:22:47]

the allowed transition states. So we're saying, where can you move from each of these different statuses?

**George Fang** [00:22:53]

So I can add a transition and say, hey, when you're in the in-progress status, you're allowed to move to hold, review, or done. We've obviously already defined this, so it would be a bit redundant.

**George Fang** [00:23:05]

But then I think another really important piece here is, before you can move from one status to another, you have to turn on certain conditions, or certain conditions need to be true. And so here, within the conditions, I can add a condition.

**George Fang** [00:23:16]

Where it's really… it's utilizing all these other important ticket fields that come natively within Serval, like the status, the priority, the assignee, etc, but then can also utilize your own custom fields. So I think what's most important here is, hey, before we move on to the done, or to the review.

**George Fang** [00:23:33]

I want a resolution code. I want to know, did this get resolved successfully? Was this, you know, canceled? Was this resolved unsuccessfully? I want a resolution summary, and so what we've done here is we say, resolution code and resolution summary need to be set before we're allowed to move on from in progress to review.

**George Fang** [00:23:50]

Finally, I want to call out the automation piece, and where we can start to build that out. So we have some status entry workflows, where this is saying whenever a ticket moves from one status to another, a workflow fires off that does any action that you want.

**George Fang** [00:24:05]

In this case, we have, on entry to review, we're going to fill in the major incident and resolution summary automatically, and so that's kind of AI helping us out and filling out these descriptors on the ticket itself.

**George Fang** [00:24:17]

Other, you know, interesting workflows that I've seen is when a major incident enters that first status, in maybe,

**George Fang** [00:24:27]

Let's see…

**George Fang** [00:24:28]

When it enters the approved status, that this is, like, the initial status of a major incident, we want to open up a channel in Teams or Slack or email and send out a notification saying, hey, we've got this current major incident we're working on, see this thread for any details or updates on this ticket.

**George Fang** [00:24:45]

So given that, let's go back to this incident where a computer is not connecting to a VPN, and let's say I'm starting to get hundreds of these, where people, you know, of all different

**George Fang** [00:24:54]

types of laptops are having issues with our VPN, it seems like there might be a bigger outage. And so I can go up to the ticket itself and say, propose as a major incident.

**George Fang** [00:25:03]

And obviously I can see… seeing hundreds.

**George Fang** [00:25:08]

of users with VPN.

**George Fang** [00:25:12]

issues.

**George Fang** [00:25:16]

I'm gonna propose a major incident. So, as an agent on the platform, that's something that you could do, given those capabilities, or given that permission, is propose a ticket as a major incident, which would then go through an approval or screening routing. And so.

**George Fang** [00:25:30]

Back on the major incident.

**George Fang** [00:25:33]

ticket type page. These three sections, status, transitions, and custom fields, are what we see on every ticket type, but some things that are unique to major instances is that ability to promote an incident to a major incident.

**George Fang** [00:25:45]

So, what we've done here is configured, and this is installable, when you install the major incident ticket, you'll also install this promotion workflow, which is fully editable and configurable.

**George Fang** [00:25:56]

But what we've done is we've said, hey, we want to run this promote to major incident workflow whenever we propose a major incident.

**George Fang** [00:26:02]

And what this workflow does is it identifies the incident.

**George Fang** [00:26:06]

It looks up all the incident details from the ticket.

**George Fang** [00:26:09]

It notifies Doug, who's our major incident manager.

**George Fang** [00:26:13]

and then it posts a company-wide outage alert to the outage alerts channel. And so, going over into Teams.

**George Fang** [00:26:19]

I can see that, hey, Serval has just posted this company-wide outage alert to my alerts channel.

**George Fang** [00:26:25]

where it's saying, you know, what is the service affected, estimated time to fix, the link to this specific ticket that I can go look on, so this kind of helps alert the rest of the company, or whoever's involved with this outage alerts, channel, that this outage is happening.

**George Fang** [00:26:40]

We can configure this promotion to have, you know, several different layers of alerting and approval workflows as well, so that this doesn't just automatically happen. In this case, you know, I'm the approver, and so this has automatically happened.

**George Fang** [00:26:52]

And what you'll see here is this ticket that was an incident has now converted to a major incident.

**George Fang** [00:27:00]

So… Before I pause for questions, I want to cover one last thing, which is, how do…

**George Fang** [00:27:07]

incidences promote two major incidences. And this can happen in three different ways. One, which is that manually pressing the promotion on a ticket, which you saw me do. I'm an agent, I've come to this ticket, and I've said, yeah, actually, based off of, like, some more context that I have about the situation, you know, personally, I think that this should be promoted to a major incident, so I'm gonna do so manually with that button with the three dots.

**George Fang** [00:27:27]

The second way that this happens is Serval's going to infer this,

**George Fang** [00:27:33]

Kind of for you. And so, what Serval does is it actually looks at any incident that comes through with priority high or urgent, those top two priorities. It's going to then kick off a flow to read the description of this ticket and determine if it should become a major incident.

**George Fang** [00:27:49]

I'll simulate that example. If I'm an end user and I come in with an incident saying, hey, every cloud… every cloud resource is down, no one's able to access anything, this is impacting the entire company, this would be something to me that's signaling, yeah, this is a major incident.

**George Fang** [00:28:03]

There's a lot of, like, key descriptors or key words in here that are making, you know, pointing the… pointing the Serval agent to believe that this should be promoted to a major incident, and so Serval can kick off that flow for you.

**George Fang** [00:28:15]

Now, obviously, you can enable there to be approvals so that this doesn't just happen every time. This is something that… or that doesn't just automatically promote to a major incident. This is something that has to go through a review stage first.

**George Fang** [00:28:27]

See someone, you know, that someone has to approve or check off on this becoming a major incident, depending on the kind of consequences that creating a major incident might have for your company.

**George Fang** [00:28:37]

So, you'll see here that on this ticket I created, every single cloud resource is down. Serval has actually automatically kicked off this promote to Major Incident Flow.

**George Fang** [00:28:45]

And this incident is now a major incident. So, that's kind of Serval being proactive about this approach, and doing more of that research for you.

**George Fang** [00:28:53]

Okay. And then the third option for how Serval does this, a more deterministic route, you can configure automatic proposals and automatic proposal rules within the ticket type. So I can add a rule that says, this is gonna be urgent tickets.

**George Fang** [00:29:09]

And so, I say, hey, Serval, I've already built out a really strong description for when a ticket should be classified as urgent. I don't want you to do any more thinking, I want you to just trust that description that I've given you for priorities, and always make this a major incident. So I could say, if a priority is urgent.

**George Fang** [00:29:29]

This is saying, if a property is urgent, just always make it a major incident. You know, don't ask me anything else about it, I want this to be a major incident.

**George Fang** [00:29:37]

So, that's that third option where you can set more deterministic rules for major instances being set.

**George Fang** [00:29:44]

Cool. Okay, I'll pause there and answer questions about major instances here.

**Davison Chung** [00:29:50]

Yeah, a couple questions about SLAs, and I think, you know, a little bit about what you were saying right there. So one, like, can you just show quickly how to attach SLAs, based on different incidents?

**Davison Chung** [00:29:59]

Yeah. It's in different services.

**George Fang** [00:30:02]

So, going back to Team Workspace settings, under the ticketing section, I can go find SLA rules, and here, each SLA has a set of rules or policies. So, Major Incident Acknowledgement, this is the name of that.

**George Fang** [00:30:15]

what I would do here, or what I would do in your case, is I would set up attachment criteria. So here we have, attachment criteria if a ticket type is any of, and I would say I want this to be, if a ticket type is a major incident.

**George Fang** [00:30:27]

And…

**George Fang** [00:30:30]

You know, maybe that's my only conditions. That means that this SLA will just auto-attach on the ticket anytime a major incident is created.

**George Fang** [00:30:38]

So I won't save that here. I'll go back to the tickets.

**George Fang** [00:30:42]

And I would say, so, that SLA would then automatically attach on the ticket. I can always manually attach a ticket here.

**George Fang** [00:30:49]

But in that SLA section that I was showing earlier, you can attach

**George Fang** [00:30:54]

any sort of attachment criteria rules, and this is related to, hey, if a ticket comes in and it's in a specific group, the requester is in a specific group, then auto-attach this SLA. If it reaches… if it's this priority, attach this SLA. If it's a given category, or a given… or it's been assigned to a specific assignment group, then it should attach this SLA. So, it's a very flexible process.

**George Fang** [00:31:14]

I think that there's another Serval 101 training that's probably more specifically built out for SLAs that can help answer those questions there.

**Davison Chung** [00:31:21]

Yeah, ITSM… Serval 101 goes over ticketing and all the features of ticketing in more depth that covers a lot of this. I think this is connected to a question, which is, can you configure the notifications that escalate up the chain based on certain criteria? For example, like, if a major… if an incident isn't updated in 20 minutes, can it be escalated, or if it hasn't changed state?

**George Fang** [00:31:45]

Yeah, and that would be a really good use case of status entry workflows. So basically, what you could do is… I mean, you could have this key off in multiple ways. If it's an incident, you could say, create, hey, catalyst, create a workflow so that when an incident ticket is created, it sets a 20-minute timer.

**George Fang** [00:32:00]

To check back on that ticket, if there hasn't been any movement on that ticket, escalated to a major incident, right?

**George Fang** [00:32:06]

Or, if you're on a specific major incident ticket, and you're saying.

**George Fang** [00:32:10]

We should have a workflow that kicks off when this ticket enters the approved state.

**George Fang** [00:32:14]

That says, you know, check every hour for an update, or maybe every hour, leave an update on this ticket, or send an update to the company's outage alerts channel.

**George Fang** [00:32:26]

given, like, the context of this ticket, send a new update every hour. And so, these are things that, with a mix of status entry workflows, or ticket creation workflows, you can configure all these different possibilities.

**Davison Chung** [00:32:37]

Yeah. And so when you have, multiple incident tickets that are linked to a major incident, how does Serval… does Serval thread those together? Does it escalate every individual ticket? How does that look?

**George Fang** [00:32:48]

Yeah, that's a great question. So, as an end user, let's say I come in with another request saying, unable to connect to the VPN.

**George Fang** [00:32:58]

you know, this would, you know, this would be a similar ticket from… in this example, we're pretending that this is from an additional user besides the one persona that I have here that, you know, I kicked off the original request here, but let's say Person B comes in, also mentions some issue with their VPN.

**George Fang** [00:33:13]

what is Serval gonna do? Serval's gonna say, hey, there's already an open, related, or possibly related VPN incident. It's gonna give me that link to that ticket, and what's really nice here is, on the major incident itself.

**George Fang** [00:33:25]

I can now see… Let me ref… oh, no, I'm on…

**George Fang** [00:33:29]

the wrong one. So if I go to the VPN major incident.

**George Fang** [00:33:33]

I can actually see all the linked tickets that are coming through now on that major incident. So…

**George Fang** [00:33:37]

let's, you know, let's say I have a major incident, and I'm getting hundreds and hundreds of tickets. All those tickets are going to be linked down here, and then I can actually send a broadcast or send a message blast to all those tickets at the same time using this broadcast button. So I can say, VPN issue is being investigated.

**George Fang** [00:33:57]

Stay tuned.

**George Fang** [00:34:00]

for more updates in… and then I can maybe say, recommend them, join the outage alerts channel.

**George Fang** [00:34:09]

Right.

**George Fang** [00:34:10]

And so, sending that as a broadcast, it's going to broadcast to all of my linked tickets, and as the end user, who may not have access to that major incident, I can see that broadcast coming from the major incident, and I can update all of my stakeholders at once.

**Davison Chung** [00:34:26]

Cool. And say, okay, let's say now that you have an incident that comes in, but it's actually not an incident, and something isn't broken, so can you convert it back to a request, or some… a different ticket type?

**George Fang** [00:34:36]

Yep, exactly what we showed before. I can take this incident.

**George Fang** [00:34:40]

hit the three dots, reclassify this as a request. And so it just transitions that incident back to request.

**Davison Chung** [00:34:46]

Cool. Alright, within… so, many questions, which is great, please keep them coming. Within automatic proposals, can you have natural language to auto-propose an incident, such as, if there are a thousand incidents generated within 15 minutes from this location, then propose a single incident record as major.

**Davison Chung** [00:35:05]

I think the answer would be, yes, you can do that.

**George Fang** [00:35:08]

Yeah, definitely. I think that's a really good use of background agents, where you'd want to configure a background agent that's sort of listening for these tickets. It runs, you know, every 30 minutes, or every hour, or whatever your cadence is. It checks for collections of tickets that seem to be expressing the same incident, and then creating a major incident related to those, and then automatically linking all of those pre-existing incident tickets to the major incident.

**George Fang** [00:35:32]

So this is something that, you know, as an agent, you could configure yourself, but as configuring a background agent can help proactively take care of this.

**George Fang** [00:35:40]

Yes.

**Davison Chung** [00:35:40]

Definitely. And you can also trigger the background… could you trigger the background agent off of, like, you know, whenever an incident is… is request… you know, is triggered or submitted, like, do this scan.

**George Fang** [00:35:52]

Yeah, exactly. And that would be another good use case, or another way to do this is, on every incident ticket creation, it kicks off a workflow to check all the other open instances at the time, see if they're related. If they are, propose a major incident, or if they are, alert somebody to look into these, like, related incidences.

**Davison Chung** [00:36:09]

Totally.

**Davison Chung** [00:36:10]

Alright. Let's see…

**George Fang** [00:36:15]

In the interest of time…

**Davison Chung** [00:36:17]

Yeah.

**George Fang** [00:36:17]

It might be good, maybe we answer one more, and then we'll move on to problem tickets.

**Davison Chung** [00:36:21]

Okay, okay. There's a question about change management, we're about to get to that. Can Serval Incident Alerting or engagement interact with other mechanisms, such as XMatters? I'm not sure what XMatters is, maybe you do, George, but…

**George Fang** [00:36:35]

I am not aware of what XMatters is, but if… if that's…

**George Fang** [00:36:45]

I think… Andrew, correct me if I'm wrong, is X Matters a alerting platform?

**George Fang** [00:36:51]

Reliable incident management, automated alerts, okay, great, yeah, so I actually just set this up with another customer the other day, where we have alert ops, which I'm… I'm gonna make this, you know, crude assumption that those are similar, or maybe function similarly.

**George Fang** [00:37:04]

where when a major incident is proposed, it actually fires before it becomes a major incident, it fires off an alert, an alert ops, that notifies on-call people that a major incident has been proposed. That on-call person then goes to the ticket.

**George Fang** [00:37:19]

And approves the first… the first gate of…

**George Fang** [00:37:22]

approvals for it to become a major incident. When that's promoted, or when that's approved, it then kicks off another alert in AlertOps that notifies the major incident manager, who then comes into the ticket and does the final round of approvals. Once both gates of approvals have been met, it then becomes a major incident. So, that's how you could build workflows to queue into other external systems that you use for alerting, to kind of queue into incidences and major instances.

**George Fang** [00:37:48]

Great.

**Davison Chung** [00:37:49]

Great. I'm gonna answer as many as I can in text, but we'll get to some of the other questions around change and other pieces, in different places. So, George, I'll let you keep going.

**George Fang** [00:37:56]

Yeah, and I'll try to save time at the end to cover more of these questions as well. But I just want to make sure that I can cover all the different ticket types, so that really is a good summary of major instances. Now, I think, like, the next…

**George Fang** [00:38:08]

piece in this story is, okay, great, we've got this major incident, we want to open, or we've got an incident or a major incident, we want to open a problem to help troubleshoot. I think, like, the core thing to note is.

**George Fang** [00:38:18]

like, bringing this back to ITIL, where the focus of ITIL is providing value, not just completing tasks, how can these… how can this ticket system help you provide value to your company? And that's configuring these different tickets to… to automate certain actions, or help you with that process of

**George Fang** [00:38:32]

Identifying the incident, promoting this to major incident, to notify the correct stakeholders, doing the right investigations and research on this ticket in a controlled and, like, automated way, and so that's where you can utilize problem tickets.

**George Fang** [00:38:45]

So, I think a really cool thing to call it here, then, is gonna be this derive function. So, from a major incident, I go to the top right where the three dots are, and I say.

**George Fang** [00:38:55]

derived ticket. And so there's a few different options that can derive, you know, a problem or a change, we'll get into that change later, but let's say I want to just derive a problem from this major incident. What's really cool is Serval's going to pre-fill this problem ticket.

**George Fang** [00:39:08]

With a title, description, and then also give me some analysis here, filling in more custom fields from the problem itself. So, is this a known error? No, we don't have any other existing errors like this in our knowledge base or in other tickets.

**George Fang** [00:39:22]

And then for workarounds, it's… this is actually something that Serval's helped me fill in from our knowledge base. So, fully quit Tailscale, reopen it, sign with Okta, you know, whatever that might be.

**George Fang** [00:39:32]

So, that's that really neat part here, where Serval can derive and kind of create this ticket for me.

**George Fang** [00:39:37]

I press Create Ticket, and then this is going to kick off a problem ticket, which then would follow the same flow that, I defined here in problem ticket, which, now at this point, should look redundant and repetitive, where I've got my statuses, my transitions, and my custom fields.

**George Fang** [00:39:53]

For a problem ticket, I've specifically defined these five statuses. I don't have any status entry workflows configured, but I do have status transition, allow status transition states configured.

**George Fang** [00:40:05]

So back on this ticket, it's opened a problem ticket for me, and from here, I can, you know, move on to the appropriate statuses, as defined. I think one thing to also call out here, which I didn't showcase earlier, is status transitions, and then with those conditions, what does that look like?

**George Fang** [00:40:22]

In this case, maybe I want to move on to known error, but I'm only able to do that once I configure this root cause.

**George Fang** [00:40:29]

So, on the top here, I can say, okay, great, I'm able to move to done, but I'm not able to move to known area because root cause is required. So I click on this action item and say, you know, the root cause is the VPN provider is experiencing

**George Fang** [00:40:46]

an outage.

**George Fang** [00:40:50]

Something like that. Once that is complete, I can then move on to go… I can go to the known error. And then again, I'm on known error. Now there's more information that I need to fill up before I'm allowed to move on to done. So that's showcasing how you can use conditions to gate the movement from… of that ticket from status to status.

**George Fang** [00:41:09]

Cool.

**George Fang** [00:41:11]

So, that was a problem from a very high level, I think.

**George Fang** [00:41:14]

to bring this back to reality and make this more real, you would want to configure more of those status entry workflows, where, hey, I just moved to known error. If I had a status entry workflow configured, where upon entry to the known error status, a workflow kicked off that maybe notified certain stakeholders, or did a specific investigation.

**George Fang** [00:41:32]

or looked into, some of my other third-party applications to, I don't know, find more information to make this ticket.

**George Fang** [00:41:41]

Or to help me do the problem investigation on this ticket.

**George Fang** [00:41:47]

Cool.

**George Fang** [00:41:49]

So one thing to note here is, again, only managers or agents on the platform will open these, usually by deriving.

**George Fang** [00:41:57]

Background agents can open problem tickets as well, so you can fully automate this system. But what's important to know is end users will never see these problems unless they're added as subscribers to the ticket. They will feel the problem resolution happening through updates on their incident ticket.

**George Fang** [00:42:13]

So…

**George Fang** [00:42:14]

From here, I think what's also really nice is you can set up background agents and workflows so that AI is proposing these remediations, creating knowledge articles, or even creating workflows so that problems like these or instances like these don't happen again, or are able to be solved with a resource in the future.

**George Fang** [00:42:34]

Cool. Okay. Finally, I want to show you, before I open up for questions.

**George Fang** [00:42:39]

is change tickets. So let's say I figured out that it is an issue with the VPN. Maybe we want to switch VPN providers, which would be kind of like a large

**George Fang** [00:42:47]

change management system, what I could do is I could open a change ticket from a major incident, so that, one, we have that linkage between tickets and that strong system of record that keeps this whole process unified. I can say, if I'm in that CAB meeting, and I say, alright, great, why are we doing this change? Okay, that's because this links back to this major incident, which was actually spawned off from this user submitting an incident two weeks ago.

**George Fang** [00:43:10]

So by keeping that chain of linked tickets together, we're really following that story path. So from a major incident, again, I can go to derive.

**George Fang** [00:43:18]

And then instead of problem, I can choose change.

**George Fang** [00:43:23]

And then, within change, I can choose any of these different subtypes. So we have emergency changes, we have normal changes, and we have standard changes. Maybe this is blocking, you know, my company's ability to do any work, and so I need this to be an emergency change.

**George Fang** [00:43:35]

Otherwise, I can configure a normal or a standard change.

**George Fang** [00:43:39]

Now, before I submit this, I want to show you what does that change type look like, and how do you configure that within Serval. So again, we'll go over to Manage Ticket Types, we'll turn on change, and then we can enter the change model.

**George Fang** [00:43:50]

Change is one of those unique ones where Serval has built-in installable change models. If I hit install, or in this case, reinstall, because I've already installed change models, there's three that are, you know, one click away. Immersion change, normal change, and Standard Change.

**George Fang** [00:44:05]

Here we've also configured the need for approvers, and so the reason why you'd have to configure an approver here is because we have some status entry workflows on change tickets that require approval before those workflows are run. And that might be that,

**George Fang** [00:44:21]

If we dive into the emergency change ticket.

**George Fang** [00:44:24]

We can look at some of these status entry workflows.

**George Fang** [00:44:28]

Where, unauthorized.

**George Fang** [00:44:30]

When we enter the state of authorize, it's going to run this authorized emergency change workflow, and it's going to require the approval of somebody in the IT ECAB group to stamp that work… to stamp that workflow and fully validate that this has been authorized.

**George Fang** [00:44:48]

Great.

**George Fang** [00:44:52]

Within Change, we also have these custom fields built in for assessment, planning, scheduling, and closure.

**George Fang** [00:44:58]

One piece that I want to call out here is that scheduling field, which… let me show you what that looks like on a live ticket. So, once I've created this emergency change, let me make this a normal change.

**George Fang** [00:45:11]

I'm going to create this ticket.

**George Fang** [00:45:16]

Again, Serval has filled out the title and description for me based off of the context of the major incident, and is also going to help fill in all these other fields.

**George Fang** [00:45:25]

something that's really nice to do is, when I am setting up these custom fields, so maybe I'm gonna go to Assess.

**George Fang** [00:45:32]

Okay, great, I need to set up all these different actions. I can say, can you help me…

**George Fang** [00:45:39]

fill in… Justification.

**George Fang** [00:45:49]

And so here, I'm using that co-pilot, or that Serval Catalyst agent that lives on the ticket to help me fill in these fields that I need to complete.

**George Fang** [00:46:00]

So that… that… in that time, that was… it looked really quick, that wasn't Catalyst doing that, that was actually this workflow, where we have a status entry workflow for assess, so as soon as we entered the assess state, a workflow kicked off, which is assess change, where Serval is going to identify the risk and impact, give me a risk and impact score, and then it's going to fill in these fields for me.

**George Fang** [00:46:20]

And then it auto-moved into authorize, because we have,

**George Fang** [00:46:30]

I believe AI transitions turned on, and so it's auto-moving me to the different states based off of these different conditions being set. On the left side here, you can see, hey, Serval's also given me some suggestions for these different fields that I could fill in, although, you know, Serval already went ahead and filled these in for me, which is really nice.

**George Fang** [00:46:49]

So when it comes to planning this change, though, I would go in and enter my plan change date. Maybe I want to do this on the 27th, it's gonna start on the 27th.

**George Fang** [00:46:58]

And then it's going to end on… 28th.

**George Fang** [00:47:05]

Serval's actually going to flag all of my scheduled conflicts.

**George Fang** [00:47:09]

So, you can see here that there's 3 different blackout windows that I'm actually overlapping. We have an AWS migration happening at the same time that we've… we've…

**George Fang** [00:47:17]

deemed no other change can happen, because this is such a large change. We don't want any other changes happening, so I'm flagging that as a blackout window.

**George Fang** [00:47:24]

We have Sunday morning freezes, and then we have weekend change freezes that prevent me from changing… doing a change on the weekend. And to answer, you know, where is that set up? That's done, again, in the team workspace settings, under General, and then under Schedules.

**George Fang** [00:47:39]

I can create a new schedule, and I can deem this schedule to either be work hours, which is, you know, something we can cover in another Serval 101 session, or blackout, which is basically saying Serval isn't allowed to… we're saying no changes are allowed to take place during this blackout window.

**George Fang** [00:47:54]

And you can see we already have a bunch of blackout windows configured, where we don't want changes to take place. And so that's why this is flagging, hey, choose a different time, I have to go back to the planned start date.

**George Fang** [00:48:04]

Change this to maybe 29th.

**George Fang** [00:48:07]

Let's see, does that conflict with anything?

**George Fang** [00:48:11]

It's gonna be a one-day change on the 29th, and we are good to go.

**George Fang** [00:48:17]

Cool.

**George Fang** [00:48:18]

Alright, I think the last two ticket types to cover, then, would be

**George Fang** [00:48:28]

Task types, and then custom types. Tasks is gonna be this much more smaller, rudimentary type of ticket, where we've got these four built-in statuses, open, in progress, done, and canceled, which will not be configurable, but we do have custom fields that can live on that task type. Task types… tickets are always children of another ticket.

**George Fang** [00:48:47]

So, within a ticket itself, I can go and create a task and say, George task.

**George Fang** [00:48:53]

Do something.

**George Fang** [00:48:55]

Create this task.

**George Fang** [00:48:57]

And then you'll see that this task

**George Fang** [00:49:00]

is when I close this out.

**George Fang** [00:49:02]

If I click into this task, it's going to show me the cookie trail of where that task comes from, and it's always going to be a child of another ticket.

**George Fang** [00:49:10]

And then finally, to wrap it all up.

**George Fang** [00:49:12]

there are custom ticket types, so if I turn this on, this is now that ability to say, hey, go wild, we've shown you all these built-in ITIL types, you can now build your own custom ticket type using,

**George Fang** [00:49:25]

all of those primitives that we previously discussed. So I want to create a new model. Maybe this is going to be my, legal tickets.

**George Fang** [00:49:34]

And I can configure the different status life cycles for those ticket types, status entry workflows, the allowed status transition states, and then custom fields. So, all the same primitives we just talked about on all those other ticket types can also exist on your custom ticket.

**George Fang** [00:49:50]

Cool.

**George Fang** [00:49:51]

Okay, I know that was a lot, so I'll pause now. I think we have 7 minutes left for questions on any of those ticket types.

**Davison Chung** [00:49:57]

Yes, thank you, George. Lots of great questions in the chat, I'm gonna… we're gonna do our best. Okay. We went over change management, we don't have anything natively for release management yet. Do you have any thoughts, George, on how teams are handling this, whether this is upcoming, or if it would be a custom ticket type?

**George Fang** [00:50:13]

Yeah, so what… I would resolve this in two different ways. I think if release is similar enough to change ticket types, what I would do is build your own change model. And so, what I've seen a lot of other people do is we have these built-in three models, which you'll see because they've got the Serval logo here.

**George Fang** [00:50:28]

But you can add your own change model, which, for your case, I would say this is a release model. And I would use these templates as sort of, like, guiding principles for maybe the kind of custom fields you want to collect.

**George Fang** [00:50:38]

or getting inspiration on the types of workflows that you want to, you know, automatically queue off on each of these different status transitions. But you can either make a new change model, or you can make your own custom ticket type.

**Davison Chung** [00:50:52]

Cool.

**Davison Chung** [00:50:53]

Alright, let's say that you have a change process that requires 2 to 4, you know, varying levels of approval based on the affected server, application, customer, etc. How can Serval support that sort of complex approval, setup?

**George Fang** [00:51:08]

Yeah, that's a great question.

**George Fang** [00:51:10]

So, when you install these change models, these workflows get installed for you out of the box, but like any other workflow on the platform, I can always go to my workflows and edit and configure this. So, I think these are gonna be…

**George Fang** [00:51:26]

Change management…

**George Fang** [00:51:32]

authorized change, let's say it's this authorized change one, and we want to add additional approvals, I can ask Catalyst to say, hey, add in these additional approval steps.

**George Fang** [00:51:42]

And then, to your question, but render these approvals conditionally based off of the service that it's impacting. And that could be, hey, based off of the asset that this is coming from.

**George Fang** [00:51:53]

If I could show you a ticket type as an example.

**George Fang** [00:51:58]

in these changes, you know, I can always add associated items.

**George Fang** [00:52:03]

from my… my database, and I can say, if this is a… if this change ticket is

**George Fang** [00:52:09]

affecting an asset that lives in cloud resources, then I want you to queue off another approval step for this person or for this group of people. And so, I think to answer your question is just anything can be configured and edited within Catalyst itself.

**George Fang** [00:52:23]

Those out-of-the-box workflows aren't set in stone.

**Davison Chung** [00:52:27]

Yeah, awesome. Alright. In this scenario, they have a root cause codification model for problem tickets. Can Serval, you know, establish the best codes based on information available in the tickets to help them do their root cause

**Davison Chung** [00:52:43]

classification and analysis. I think the answer is gonna be yes, but George, how would you set that up?

**George Fang** [00:52:49]

Yeah, definitely. I would leverage knowledge articles here, where if you guys have that, you know, list of codes and those definitions on when those codes apply.

**George Fang** [00:52:57]

By having Serval set those ticket types.

**George Fang** [00:53:00]

or by having that toggle enabled for, we're in problem… custom fields, being able to be set with AI, if we have, hey, these are… this is the PIR code, and then we have a knowledge base that defines what these codes are and when they should be used, Serval's going to be able to automatically assign these fields and take care of that for you. Alternatively, you can always

**George Fang** [00:53:20]

Bring those, maybe, codes or definitions, descriptions on the fly, and work with Catalyst directly on the ticket.

**George Fang** [00:53:28]

So I've got my problem ticket, and I'm saying, hey, Catalyst, you know, based off the knowledge article that I have on ticket… on problems and problem codes, can you help define or help me identify what the right code would be for this ticket, given the ticket context?

**Davison Chung** [00:53:43]

Cool. We have a question here, whether emergency change can send an automatic notification. I think the answer is yes, you would set that up as a workflow that triggers on any emergency change ticket type, so answer is yes there. And there's a question here I don't understand, but maybe you do, George, which is, do we have a conflict deduction where you schedule a change for a particular configuration item, and there is already a change ongoing for the CI?

**George Fang** [00:54:08]

Yeah, that's a great question. So, that would also… you'd want to configure that as a workflow, so that upon entrance to a certain status, I think what you'd want to have configured is, for step one, before you move on to

**George Fang** [00:54:21]

that status field, you'd want to have the, identified CI linked.

**George Fang** [00:54:27]

Then, upon entrance to that new status, you'd have a status entry workflow that checks, are there any active changes currently happening for that asset? If so, flag that and move this ticket to… or move this change ticket to on hold, and alert… and then, like, notify the user, either via internal note or external note, saying.

**George Fang** [00:54:46]

there's currently an active change happening for this CI. This change needs to wait. Or reach out to X, Y, and Z owner.

**Davison Chung** [00:54:56]

Cool. There's a question here, I think I'm gonna interpret it correctly, Andrew, but let me if I don't, which is basically, like, let's say that we have, we haven't done a root cause analysis yet from an incident or from a problem. Can we have Serval start to establish the questions or avenues for exploration somewhere?

**Davison Chung** [00:55:14]

Proactively.

**Davison Chung** [00:55:16]

Excuse me, to try and help the problem or incident manager.

**Davison Chung** [00:55:21]

I think this is basically asking, like, can we have Serval start to investigate incidents or problems ahead of the problem manager and structure the avenues for investigation?

**George Fang** [00:55:32]

Yeah, and that's kind of actually exactly what you're seeing here, where we've got this data entry workflow, where Serval's going to do a root cause analysis, provide me with all these details, and we can, you know, configure this workflow to add more details as well, so that as an agent, I come to this problem ticket for the first time, and there's all this information already loaded up about the problem, the remediation steps, things I should look into, etc.

**Davison Chung** [00:55:55]

All right. Michael, I know you had one more question about release management, and how release management is coming up to, you know, to the left, and then is feeding your change model. I think this is probably something that's best to be answered by your deployment team. I know, and maybe this is related, George, we have more product coming out around software development lifecycle, which maybe is related to releases as well, but, but your deployment team is going to be able to answer this specific question

**Davison Chung** [00:56:19]

in much more depth, so apologies that we don't have anything out of the box, and we don't have a lot of time to run through it here at the end here. But really, really appreciate everyone coming. This was a great session. You guys all asked an amazing amount of questions. We have more sessions next week. You can find them at the registration link, which I'll put in the chat right now. This will be going up on the Zoom channel, and so if you don't have access to that.

